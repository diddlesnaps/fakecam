require('./platform_node_webgl');

// const {asyncStorageIO} = require('./async_storage_io');
// const {bundleResourceIO} = require('./bundle_resource_io');
const {decodeJpeg} = require('./decode_image');
const {fetch} = require('./platform_node_webgl');
// const camera = require('./camera/camera');
// const camera_stream = require('./camera/camera_stream');

module.exports = {
    decodeJpeg,
    fetch,
}