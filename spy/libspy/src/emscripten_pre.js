Module.instantiateWasm = (imports, successCallback) => {
  (async () => {
    Module.adjustImports?.(imports);
    const binary = await getBinaryPromise(wasmBinaryFile);
    const res = await WebAssembly.instantiate(binary, imports);
    successCallback(res.instance, res.module);
  })();
  return {};
};

Module.connectFileSystems = (otherFS) => {
  addOnInit(() => {
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
    FS.mount(FS.filesystems.NODEFS, { root: mount, fs: otherFS }, mount);
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
  debugger;
  const major = FS.createDevice.major++;
  const proxy_device = FS.makedev(major, 0);

  FS.registerDevice(proxy_device, makeProxyDeviceStreamOps(otherFS));
  for (const dev of getProxyDevices(otherFS)) {
    FS.unlink(dev);
    FS.mkdev(dev, proxy_device);
  }
  refreshStreams(otherFS);
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
    if (!e.code) throw e;
    throw new FS.ErrnoError(ERRNO_CODES[e.code]);
  }
}

/**
 * Almost the same as proxyfs stream_ops, but adapted to proxy a device instead
 * of a file system.
 */
function makeProxyDeviceStreamOps(otherFS) {
  return {
    open(stream) {
      const otherStream = translateErrnoError(() =>
        otherFS.open(stream.path, stream.flags),
      );
      stream.nfd = otherStream.fd;
      stream.tty = otherStream.tty;
      stream.seekable = otherStream.seekable;
    },
    close(stream) {
      // flush any pending line data but don't close targetFD
      translateErrnoError(() => otherFS.close(stream.nfd));
    },
    fsync(stream) {
      translateErrnoError(() => otherFS.fsync(stream.nfd));
    },
    read(stream, buffer, offset, length, pos) {
      return translateErrnoError(() =>
        otherFS.read(stream.nfd, buffer, offset, length, pos),
      );
    },
    write(stream, buffer, offset, length, pos) {
      return translateErrnoError(() =>
        otherFS.write(stream.nfd, buffer, offset, length, pos),
      );
    },
    llseek: PROXYFS.llseek,
  };
}

function refreshStreams(otherFS) {
  FS.closeStream(0 /* stdin */);
  FS.closeStream(1 /* stdout */);
  FS.closeStream(2 /* stderr */);
  // Have to close Pyodide's stdstreams too because ProxyDeviceStreamOps.open
  // will also open in Pyodide's FS.
  otherFS.closeStream(0 /* stdin */);
  otherFS.closeStream(1 /* stdout */);
  otherFS.closeStream(2 /* stderr */);
  FS.open("/dev/stdin", 0 /* O_RDONLY */);
  FS.open("/dev/stdout", 1 /* O_WRONLY */);
  FS.open("/dev/stderr", 1 /* O_WRONLY */);
}
