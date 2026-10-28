# -*- coding: utf-8 -*-
"""ssh-gateway.py 的权限/输入校验测试（纯离线，不启动 SSH、不调用 sudo）。"""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ssh_gateway", RAG_DIR / "ssh-gateway.py")
gw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gw)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def npy_bytes(rows=2, dim=2):
    import numpy as np
    arr = np.zeros((rows, dim), dtype="<f4")
    bio = io.BytesIO()
    np.save(bio, arr, allow_pickle=False)
    return bio.getvalue()


def chunks_bytes(count=2):
    return b"".join(
        json.dumps({"id": "c%d" % i, "text": "hello %d" % i},
                   ensure_ascii=False).encode("utf-8") + b"\n"
        for i in range(count)
    )


def manifest_bytes(vectors, chunks, rows=2, dim=2, hashes=True):
    data = {"chunks": rows, "embed_dim": dim}
    if hashes:
        data["vectors_sha1"] = sha1(vectors)
        data["chunks_sha1"] = sha1(chunks)
    return json.dumps(data).encode("utf-8")


def make_files(rows=2, dim=2, hashes=True):
    vectors = npy_bytes(rows, dim)
    chunks = chunks_bytes(rows)
    manifest = manifest_bytes(vectors, chunks, rows, dim, hashes)
    return {
        "vectors.npy": vectors,
        "chunks.jsonl": chunks,
        "manifest.json": manifest,
    }


def limits(**kwargs):
    base = dict(total=1024 * 1024, vectors=512 * 1024, chunks=512 * 1024,
                manifest=128 * 1024, stream=2 * 1024 * 1024, max_line=64 * 1024)
    base.update(kwargs)
    return gw.Limits(**base)


def make_tar(entries):
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            tf.addfile(info, io.BytesIO(data))
    return bio.getvalue()


def make_special_tar(kind, name):
    bio = io.BytesIO()
    with tarfile.open(fileobj=bio, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        info = tarfile.TarInfo(name)
        if kind == "symlink":
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
        elif kind == "hardlink":
            info.type = tarfile.LNKTYPE
            info.linkname = "vectors.npy"
        elif kind == "dir":
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
        elif kind == "fifo":
            info.type = tarfile.FIFOTYPE
        tf.addfile(info)
    return bio.getvalue()


def collect_sink(store):
    def sink(name, size, src):
        data = src.read()
        store[name] = data
        return len(data)
    return sink


class TestParseCommand(unittest.TestCase):
    def test_valid(self):
        release = "a" * 40 + "-123456-2"
        self.assertEqual(gw.parse_command("baseline"), ("baseline",))
        self.assertEqual(gw.parse_command("upload " + release), ("upload", release))
        self.assertEqual(
            gw.parse_command("publish %s %s" % (release, "b" * 64)),
            ("publish", release, "b" * 64),
        )

    def test_rejections(self):
        release = "a" * 40 + "-1-1"
        bad = [
            None,
            "",
            "baseline extra",
            "upload",
            "upload " + "a" * 39 + "-1-1",
            "upload " + "a" * 41 + "-1-1",
            "upload " + "A" * 40 + "-1-1",
            "upload " + "a" * 40 + "-x-1",
            "upload " + release + "; rm -rf /",
            "upload " + release + " extra",
            "publish %s %s" % (release, "B" * 64),
            "publish %s %s" % (release, "b" * 63),
            "baseline\n",
            "baseline\0",
            "sftp",
            "bash -i",
        ]
        for raw in bad:
            with self.subTest(raw=raw):
                with self.assertRaises(gw.GatewayError):
                    gw.parse_command(raw)

    def test_release_regex(self):
        gw.check_release("0" * 40 + "-0-0")
        for value in ("a" * 40 + "-1", "a" * 40 + "-1-1-1", "g" * 40 + "-1-1"):
            with self.subTest(value=value):
                with self.assertRaises(gw.GatewayError):
                    gw.check_release(value)


class TestValidateIndex(unittest.TestCase):
    def test_valid_and_manifest_sha(self):
        files = make_files()
        digest = gw.validate_index_bytes(files, strict=True, limits=limits())
        self.assertEqual(digest, hashlib.sha256(files["manifest.json"]).hexdigest())

    def test_tampered_chunks_rejected(self):
        files = make_files()
        files["chunks.jsonl"] = files["chunks.jsonl"].replace(b"hello 0", b"HELLO 0")
        with self.assertRaises(gw.InconsistentIndex):
            gw.validate_index_bytes(files, strict=True, limits=limits())

    def test_missing_hashes_strict_rejected(self):
        files = make_files(hashes=False)
        with self.assertRaises(gw.InputError):
            gw.validate_index_bytes(files, strict=True, limits=limits())
        # baseline 兼容旧 manifest：非严格模式允许缺哈希
        gw.validate_index_bytes(files, strict=False, limits=limits())

    def test_row_count_mismatch(self):
        files = make_files(rows=2)
        files["chunks.jsonl"] = chunks_bytes(1)
        files["manifest.json"] = manifest_bytes(
            files["vectors.npy"], files["chunks.jsonl"], rows=2, dim=2
        )
        with self.assertRaises(gw.InconsistentIndex):
            gw.validate_index_bytes(files, strict=True, limits=limits())

    def test_extra_and_wrong_type_rejected(self):
        with self.assertRaises(gw.InputError):
            gw.validate_index_bytes({"vectors.npy": b"", "chunks.jsonl": b"",
                                     "manifest.json": b"{}", "x": b""},
                                    strict=True, limits=limits())

    def test_npy_header_rejects_trailing_data(self):
        files = make_files()
        files["vectors.npy"] += b"x"
        files["manifest.json"] = manifest_bytes(
            files["vectors.npy"], files["chunks.jsonl"]
        )
        with self.assertRaises(gw.InconsistentIndex):
            gw.validate_index_bytes(files, strict=True, limits=limits())


class TestUploadTar(unittest.TestCase):
    def _valid_tar(self, prefix=""):
        files = make_files()
        return make_tar([(prefix + name, files[name]) for name in gw.INDEX_FILES]), files

    def test_valid_tar(self):
        data, files = self._valid_tar()
        store = {}
        seen = gw.extract_upload_tar(io.BytesIO(data), limits(), collect_sink(store))
        self.assertEqual(seen, set(gw.INDEX_FILES))
        self.assertEqual(store, files)
        gw.validate_index_bytes(store, strict=True, limits=limits())

    def test_dot_slash_names_accepted(self):
        data, _ = self._valid_tar(prefix="./")
        store = {}
        gw.extract_upload_tar(io.BytesIO(data), limits(), collect_sink(store))
        self.assertEqual(set(store), set(gw.INDEX_FILES))

    def test_extra_file_rejected(self):
        data, files = self._valid_tar()
        data = make_tar([(n, files[n]) for n in gw.INDEX_FILES] + [("extra", b"x")])
        with self.assertRaises(gw.InputError):
            gw.extract_upload_tar(io.BytesIO(data), limits(), collect_sink({}))

    def test_missing_file_rejected(self):
        data, files = self._valid_tar()
        data = make_tar([(n, files[n]) for n in gw.INDEX_FILES[:2]])
        with self.assertRaises(gw.InputError):
            gw.extract_upload_tar(io.BytesIO(data), limits(), collect_sink({}))

    def test_path_traversal_and_absolute_rejected(self):
        for name in ("../evil", "/tmp/evil", "sub/vectors.npy", "vectors.npy/",
                     "./../evil"):
            with self.subTest(name=name):
                data = make_tar([(name, b"x")])
                with self.assertRaises(gw.InputError):
                    gw.extract_upload_tar(io.BytesIO(data), limits(), collect_sink({}))

    def test_symlink_hardlink_fifo_dir_rejected(self):
        for kind, name in (("symlink", "vectors.npy"), ("hardlink", "vectors.npy"),
                           ("fifo", "vectors.npy"), ("dir", "vectors.npy")):
            with self.subTest(kind=kind):
                data = make_special_tar(kind, name)
                with self.assertRaises(gw.InputError):
                    gw.extract_upload_tar(io.BytesIO(data), limits(), collect_sink({}))

    def test_duplicate_rejected(self):
        files = make_files()
        data = make_tar([("vectors.npy", files["vectors.npy"]),
                         ("vectors.npy", files["vectors.npy"])])
        with self.assertRaises(gw.InputError):
            gw.extract_upload_tar(io.BytesIO(data), limits(), collect_sink({}))

    def test_per_file_and_total_limits(self):
        files = make_files()
        data = make_tar([(n, files[n]) for n in gw.INDEX_FILES])
        with self.assertRaises(gw.InputError):
            gw.extract_upload_tar(
                io.BytesIO(data), limits(vectors=16), collect_sink({})
            )
        with self.assertRaises(gw.InputError):
            gw.extract_upload_tar(
                io.BytesIO(data), limits(total=32), collect_sink({})
            )

    def test_stream_limit(self):
        data, _ = self._valid_tar()
        with self.assertRaises(gw.InputError):
            gw.extract_upload_tar(
                io.BytesIO(data), limits(stream=100), collect_sink({})
            )

    def test_gzip_not_accepted(self):
        import gzip
        data, _ = self._valid_tar()
        with self.assertRaises(gw.InputError):
            gw.extract_upload_tar(
                io.BytesIO(gzip.compress(data)), limits(), collect_sink({})
            )

    def test_linkname_on_regular_rejected(self):
        bio = io.BytesIO()
        with tarfile.open(fileobj=bio, mode="w", format=tarfile.USTAR_FORMAT) as tf:
            info = tarfile.TarInfo("vectors.npy")
            info.size = 1
            info.linkname = "elsewhere"
            tf.addfile(info, io.BytesIO(b"x"))
        with self.assertRaises(gw.InputError):
            gw.extract_upload_tar(io.BytesIO(bio.getvalue()), limits(),
                                  collect_sink({}))


class TestBaselineTar(unittest.TestCase):
    def test_tar_contains_exactly_three_files(self):
        files = make_files()
        out = io.BytesIO()
        gw._write_tar(out, files)
        with tarfile.open(fileobj=io.BytesIO(out.getvalue()), mode="r:") as tf:
            members = tf.getmembers()
            self.assertEqual([m.name for m in members], list(gw.INDEX_FILES))
            for m in members:
                self.assertTrue(m.isreg())
                self.assertEqual(tf.extractfile(m).read(), files[m.name])

    def test_cmd_baseline_from_directory(self):
        files = make_files()
        tmp = tempfile.mkdtemp(prefix="qutwiki-rag-baseline-test-")
        try:
            for name, data in files.items():
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(data)
            out = io.BytesIO()
            gw.cmd_baseline(tmp, out, limits())
            with tarfile.open(fileobj=io.BytesIO(out.getvalue()), mode="r:") as tf:
                self.assertEqual(
                    {m.name for m in tf.getmembers()}, set(gw.INDEX_FILES)
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestUploadCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="qutwiki-rag-upload-test-")
        self.incoming = os.path.join(self.tmp, "incoming")
        os.mkdir(self.incoming, 0o700)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_upload_writes_release_and_is_replaceable(self):
        files = make_files()
        data = make_tar([(n, files[n]) for n in gw.INDEX_FILES])
        release = "a" * 40 + "-123-1"
        out = io.BytesIO()
        gw.cmd_upload(release, self.incoming, io.BytesIO(data), out, limits())
        target = os.path.join(self.incoming, release)
        self.assertTrue(os.path.isdir(target))
        self.assertEqual(set(os.listdir(target)), set(gw.INDEX_FILES))
        self.assertIn(release.encode("ascii"), out.getvalue())

        # 同一 release 重跑 upload 必须安全替换，而不是失败或跟随旧内容。
        out2 = io.BytesIO()
        gw.cmd_upload(release, self.incoming, io.BytesIO(data), out2, limits())
        self.assertEqual(set(os.listdir(target)), set(gw.INDEX_FILES))

    def test_upload_rejects_bad_tar_without_leaving_release(self):
        release = "b" * 40 + "-9-2"
        bad = make_tar([("vectors.npy", b"not-a-npy")])
        with self.assertRaises(gw.InputError):
            gw.cmd_upload(release, self.incoming, io.BytesIO(bad), io.BytesIO(),
                          limits())
        self.assertFalse(os.path.exists(os.path.join(self.incoming, release)))
        self.assertEqual(os.listdir(self.incoming), [])


class TestDirectoryValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="qutwiki-rag-gw-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, files, extra=None):
        for name, data in files.items():
            with open(os.path.join(self.tmp, name), "wb") as f:
                f.write(data)
        if extra:
            with open(os.path.join(self.tmp, extra), "wb") as f:
                f.write(b"x")

    def test_valid_dir(self):
        files = make_files()
        self._write(files)
        with gw.DirHandle(self.tmp) as handle:
            digest = gw.validate_index_dir_handle(
                handle, strict=True, limits=limits()
            )
        self.assertEqual(digest, hashlib.sha256(files["manifest.json"]).hexdigest())

    def test_extra_file_rejected(self):
        files = make_files()
        self._write(files, extra="junk")
        with gw.DirHandle(self.tmp) as handle:
            with self.assertRaises(gw.InputError):
                gw.validate_index_dir_handle(handle, strict=True, limits=limits())

    def test_missing_file_rejected(self):
        files = make_files()
        del files["chunks.jsonl"]
        self._write(files)
        with gw.DirHandle(self.tmp) as handle:
            with self.assertRaises(gw.InputError):
                gw.validate_index_dir_handle(handle, strict=True, limits=limits())


class TestPublishArgv(unittest.TestCase):
    def test_argv_is_fixed_and_not_shell(self):
        release = "a" * 40 + "-1-1"
        sha = "c" * 64
        argv = gw.build_publish_argv(release, sha, sudo="/usr/bin/sudo")
        self.assertEqual(
            argv,
            ["/usr/bin/sudo", "-n", "--", gw.DEPLOY_HELPER, release, sha],
        )
        with self.assertRaises(gw.UsageError):
            gw.build_publish_argv(release, "C" * 64, sudo="/usr/bin/sudo")
        with self.assertRaises(gw.UsageError):
            gw.build_publish_argv("a" * 40 + "-1-1;id", sha, sudo="/usr/bin/sudo")


if __name__ == "__main__":
    unittest.main()
