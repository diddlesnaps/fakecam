const tf = require('@tensorflow/tfjs');
const {Buffer} = require('buffer');
const gles = require('node-gles');

let debugMode_ = false;
module.exports.setDebugMode = function setDebugMode(debugMode) {
  debugMode_ = debugMode_;
}

module.exports.getDebugMode = function getDebugMode() {
  return debugMode_;
}

const fetch = require('node-fetch')

class PlatformNodeWebGL {
  /**
   * Makes an HTTP request.
   *
   * see @fetch docs above.
   */
  async fetch(path, init, options) {
    return fetch(path, init, options);
  }

  /**
   * Encode the provided string into an array of bytes using the provided
   * encoding.
   */
  encode(text, encoding) {
    // See https://www.w3.org/TR/encoding/#utf-16le
    if (encoding === 'utf-16') {
      encoding = 'utf16le';
    }
    return new Uint8Array(Buffer.from(text, encoding));
  }
  /** Decode the provided bytes into a string using the provided encoding. */
  decode(bytes, encoding) {
    // See https://www.w3.org/TR/encoding/#utf-16le
    if (encoding === 'utf-16') {
      encoding = 'utf16le';
    }
    return Buffer.from(bytes).toString(encoding);
  }

  now() {
    //@ts-ignore
    if (global.nativePerformanceNow) {
      //@ts-ignore
      return global.nativePerformanceNow();
    }
    return Date.now();
  }
}

module.exports.PlatformNodeWebGL = PlatformNodeWebGL

function setupGlobals() {
  global.Buffer = Buffer;
}

function registerWebGLBackend() {
  try {
    const PRIORITY = 5;
    tf.registerBackend('node-webgl', () => {
      const glContext = gles.createWebGLRenderingContext();

      // ExpoGl getBufferSubData is not implemented yet (throws an exception).
      tf.env().set('WEBGL_BUFFER_SUPPORTED', false);

      //
      // Mock extension support for EXT_color_buffer_float and
      // EXT_color_buffer_half_float on the expo-gl context object.
      // In react native we do not have to get a handle to the extension
      // in order to use the functionality of that extension on the device.
      //
      // This code block makes iOS and Android devices pass the extension checks
      // used in core. After those are done core will actually test whether
      // we can render/download float or half float textures.
      //
      // We can remove this block once we upstream checking for these
      // extensions in expo.
      //
      // TODO look into adding support for checking these extensions in expo-gl
      //
      //@ts-ignore
      const getExt = glContext.getExtension.bind(glContext);
      const shimGetExt = (name) => {
        if (name === 'EXT_color_buffer_float') {
          return {};
        }

        if (name === 'EXT_color_buffer_half_float') {
          return {};
        }
        return getExt(name);
      };

      //
      // Manually make 'read' synchronous. glContext has a defined gl.fenceSync
      // function that throws a "Not implemented yet" exception so core
      // cannot properly detect that it is not supported. We mock
      // implementations of gl.fenceSync and gl.clientWaitSync
      // TODO remove once fenceSync and clientWaitSync is implemented upstream.
      //
      const shimFenceSync = () => {
        return {};
      };
      const shimClientWaitSync = () => glContext.CONDITION_SATISFIED;

      // @ts-ignore
      glContext.getExtension = shimGetExt.bind(glContext);
      glContext.fenceSync = shimFenceSync.bind(glContext);
      glContext.clientWaitSync = shimClientWaitSync.bind(glContext);

      // Set the WebGLContext before flag evaluation
      tf.webgl.setWebGLContext(2, glContext);
      const context = new tf.webgl.GPGPUContext();
      const backend = new tf.webgl.MathBackendWebGL(context);

      return backend;
    }, PRIORITY);

    // Register all the webgl kernels on the rn-webgl backend
    const kernels = tf.getKernelsForBackend('webgl');
    kernels.forEach(kernelConfig => {
      const newKernelConfig =
          Object.assign({}, kernelConfig, {backendName: 'node-webgl'});
      tf.registerKernel(newKernelConfig);
    });
  } catch (e) {
    throw (new Error(`Failed to register Webgl backend: ${e.message}`));
  }
}

setupGlobals();
registerWebGLBackend();
tf.setPlatform('node-webgl', new PlatformNodeWebGL());