Module.instantiateWasm = (imports, successCallback) => {
  (async () => {
    Module.adjustImports?.(imports);
    const binary = await getBinaryPromise(wasmBinaryFile);
    const res = await WebAssembly.instantiate(binary, imports);
    successCallback(res.instance, res.module);
  })();
  return {}
}



/**
 * Calls the callback and handle node EAGAIN errors.
 *
 * In the long run, it may be helpful to allow C code to handle these errors on
 * their own, at least if the Emscripten file descriptor has O_NONBLOCK on it.
 * That way the code could do OTHER_ periodic tasks in the delay loop.
 *
 * This code is outside of the stream handler itself so if the user wants to
 * inject some code in this loop they could do it with:
 * ```js
 * read(buffer) {
 *   try {
 *     return doTheRead();
 *   } catch(e) {
 *     if (e && e.code === "EAGAIN") {
 *       // do periodic tasks
 *     }
 *     // in every case rethrow the error
 *     throw e;
 *   }
 * }
 * ```
 */
function handleEAGAIN(cb) {
  while (true) {
    try {
      return cb();
    } catch (e) {
      if (e && e.code === "EAGAIN") {
        // Presumably this means we're in node and tried to read from/write to
        // an O_NONBLOCK file descriptor. Synchronously sleep for 100ms as
        // requested by EAGAIN and try again. In case for some reason we fail to
        // sleep, propagate the error (it will turn into an EOFError).
        if (syncSleep(100)) {
          continue;
        }
      }
      throw e;
    }
  }
}

function readWriteHelper(stream, cb, method) {
  let nbytes;
  try {
    nbytes = handleEAGAIN(cb);
  } catch (e) {
    if (e && e.code && Module.ERRNO_CODES[e.code]) {
      throw new FS.ErrnoError(Module.ERRNO_CODES[e.code]);
    }
    if (isErrnoError(e)) {
      // the handler set an errno, propagate it
      throw e;
    }
    console.error(`Error thrown in ${method}:`);
    console.error(e);
    throw new FS.ErrnoError(Module.ERRNO_CODES.EIO);
  }
  if (nbytes === undefined) {
    // Prevent an infinite loop caused by incorrect code that doesn't return a
    // value
    // Maybe we should set nbytes = buffer.length here instead?
    console.warn(
      `${method} returned undefined; a correct implementation must return a number`,
    );
    throw new FS.ErrnoError(Module.ERRNO_CODES.EIO);
  }
  if (nbytes !== 0) {
    stream.node.timestamp = Date.now();
  }
  return nbytes;
}

const DEVS = {};

let OTHER_FS;
const stream_ops = {
  open: function (stream) {
    const targetFD = FS.minor(stream.node.rdev);
    stream.targetFD = targetFD;
    const otherStream = OTHER_FS.getStreamChecked(targetFD);
    stream.tty = otherStream.tty;
    stream.seekable = false;
  },
  close: function (stream) {
    // flush any pending line data. Don't close targetFD!
    stream.stream_ops.fsync(stream);
  },
  fsync: function (stream) {
    OTHER_FS.fsync(stream.targetFD);
  },
  read: function (stream, buffer, offset, length, pos) {
    return OTHER_FS.read(OTHER_FS.getStreamChecked(stream.targetFD), buffer, offset, length, pos);
  },
  write: function (stream, buffer, offset, length, pos /* ignored */) {
    return OTHER_FS.write(OTHER_FS.getStreamChecked(stream.targetFD), buffer, offset, length, pos);
  },
};

function refreshStreams() {
  FS.closeStream(0 /* stdin */);
  FS.closeStream(1 /* stdout */);
  FS.closeStream(2 /* stderr */);
  FS.open("/dev/stdin", 0 /* O_RDONLY */);
  FS.open("/dev/stdout", 1 /* O_WRONLY */);
  FS.open("/dev/stderr", 1 /* O_WRONLY */);
}

Module.connectStdStreams = (otherFS) => {
  OTHER_FS = otherFS;
  const major = FS.createDevice.major++;
  DEVS.stdin = FS.makedev(major, 0);
  DEVS.stdout = FS.makedev(major, 1);
  DEVS.stderr = FS.makedev(major, 2);

  FS.registerDevice(DEVS.stdin, stream_ops);
  FS.registerDevice(DEVS.stdout, stream_ops);
  FS.registerDevice(DEVS.stderr, stream_ops);
  FS.unlink("/dev/stdin");
  FS.unlink("/dev/stdout");
  FS.unlink("/dev/stderr");

  FS.mkdev("/dev/stdin", DEVS.stdin);
  FS.mkdev("/dev/stdout", DEVS.stdout);
  FS.mkdev("/dev/stderr", DEVS.stderr);

  refreshStreams();
}
