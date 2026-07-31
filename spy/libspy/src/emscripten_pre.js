debugger;
Module.instantiateWasm = (imports, successCallback) => {
  (async () => {
    Module.adjustImports?.(imports);
    wasmBinaryFile ??= findWasmBinary();
    const {instance} = await instantiateArrayBuffer(wasmBinaryFile, imports);
    successCallback(instance);
  })();
  return {};
};

Module.connectFileSystems = (otherFS) => {
  addOnPostCtor(() => {
    mountProxyFSRoots(otherFS);
    connectStdStreams(otherFS);
  });
};

/**
 * Make root folders in libspy Emscripten point to root folders in Pyodide
 * emscripten. We can't do it for /dev, /lib, or /proc so skip those.
 */
function mountProxyFSRoots(otherFS) {
  for (const mount of getProxyFSRoots(otherFS)) {
    FS.mkdirTree(mount);
    FS.mount(FS.filesystems.PROXYFS, { root: mount, fs: otherFS }, mount);
  }
}

function getProxyFSRoots(otherFS) {
  const filteredDirs = new Set([".", "..", "dev", "lib", "proc"]);
  return otherFS
    .readdir("/")
    .filter((dir) => !filteredDirs.has(dir))
    .map((dir) => "/" + dir);
}

/**
 * Connect std streams in libspy Emscripten to the std streams in Pyodide
 * Emscripten. This is meant to closely approximate what you'd get by removing
 * the /dev directory and mounting it as a PROXYFS but that doesn't work because
 * /dev/shm cannot be removed.
 */
function connectStdStreams(otherFS) {
  const major = FS.createDevice.major++;
  const proxy_device = FS.makedev(major, 0);

  const stream_ops = makeProxyDeviceStreamOps(otherFS);
  FS.registerDevice(proxy_device, stream_ops);
  for (const dev of getProxyDevices(otherFS)) {
    FS.unlink(dev);
    FS.mkdev(dev, proxy_device);
  }
  refreshStreams(otherFS, stream_ops);
}

function getProxyDevices(otherFS) {
  const filteredDevices = new Set([".", "..", "shm"]);
  return otherFS
    .readdir("/dev")
    .filter((dev) => !filteredDevices.has(dev))
    .map((dev) => "/dev/" + dev);
}

/**
 * otherFS throws an otherFS.ErrnoError, we need to throw an FS.ErrnoError.
 */
function translateErrnoError(cb) {
  try {
    return cb();
  } catch (e) {
    if (!e.errno) throw e;
    throw new FS.ErrnoError(ERRNO_CODES[e.errno]);
  }
}

/**
 * Almost the same as proxyfs stream_ops, but adapted to proxy a device instead
 * of a file system.
 */
function makeProxyDeviceStreamOps(otherFS) {
  return {
    open(stream) {
      let otherStream;
      if (this.refreshingStreams) {
        // Normally ProxyDeviceStreamOps.open will also open in Pyodide's FS, but
        // the standard streams are already open in Pyodide. Instead, force file
        // descriptors 0, 1, and 2 to directly point to existing Pyodide file
        // descriptors 0, 1, and 2.
        otherStream = translateErrnoError(() =>
          otherFS.getStreamChecked(stream.fd),
        );
      } else {
        otherStream = translateErrnoError(() =>
          otherFS.open(stream.path, stream.flags),
        );
      }
      stream.nfd = otherStream.fd;
      stream.tty = otherStream.tty;
      stream.seekable = otherStream.seekable;
    },
    close(stream) {
      translateErrnoError(() => {
        const otherStream = otherFS.getStreamChecked(stream.nfd);
        otherFS.close(otherStream);
      });
    },
    fsync(stream) {
      translateErrnoError(() => {
        const otherStream = otherFS.getStreamChecked(stream.nfd);
        otherFS.fsync(otherStream);
      });
    },
    read(stream, buffer, offset, length, pos) {
      if (!stream.seekable) {
        // Hack: FS.read doesn't compose properly and forces pos to 0 even if
        // the stream isn't seekable. Put it back to undefined.
        pos = undefined;
      }
      return translateErrnoError(() => {
        const otherStream = otherFS.getStreamChecked(stream.nfd);
        return otherFS.read(otherStream, buffer, offset, length, pos);
      });
    },
    write(stream, buffer, offset, length, pos) {
      if (!stream.seekable) {
        // Hack: FS.write doesn't compose properly and forces pos to 0 even if
        // the stream isn't seekable. Put it back to undefined.
        pos = undefined;
      }
      return translateErrnoError(() => {
        const otherStream = otherFS.getStreamChecked(stream.nfd);
        return otherFS.write(otherStream, buffer, offset, length, pos);
      });
    },
    llseek: PROXYFS.llseek,
  };
}

function refreshStreams(otherFS, stream_ops) {
  FS.closeStream(0 /* stdin */);
  FS.closeStream(1 /* stdout */);
  FS.closeStream(2 /* stderr */);
  stream_ops.refreshingStreams = true;
  FS.open("/dev/stdin", 0 /* O_RDONLY */);
  FS.open("/dev/stdout", 1 /* O_WRONLY */);
  FS.open("/dev/stderr", 1 /* O_WRONLY */);
  stream_ops.refreshingStreams = false;
}
