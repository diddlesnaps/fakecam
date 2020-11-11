import cv2
import numpy as np


def remove_padding_and_resize_back(resized_and_padded, original_height, original_width):
    return cv2.resize(resized_and_padded, (original_width, original_height))


def sigmoid(x, height, width):
    zeroes = cv2.UMat(np.zeros((height, width)))
    ones = cv2.UMat(np.ones((height, width)))

    subbed = cv2.subtract(zeroes, x, dtype=cv2.CV_32F)
    added = cv2.add(ones, cv2.exp(subbed), dtype=cv2.CV_32F)
    return cv2.divide(ones, added, dtype=cv2.CV_32F)


def scale_and_crop_to_input_tensor_shape(tensor,
                                         input_tensor_height, input_tensor_width,
                                         apply_sigmoid_activation):
    in_resized_and_padded = cv2.resize(tensor,
                                       (input_tensor_width, input_tensor_height))
    if apply_sigmoid_activation:
        in_resized_and_padded = sigmoid(in_resized_and_padded, input_tensor_height, input_tensor_width)

    return remove_padding_and_resize_back(in_resized_and_padded,
                                          input_tensor_height, input_tensor_width)


def is_valid_input_resolution(resolution, output_stride):
    return (resolution - 1) % output_stride == 0


def to_valid_input_resolution(input_resolution, output_stride):
    if is_valid_input_resolution(input_resolution, output_stride):
        return input_resolution
    return int(np.floor(input_resolution / output_stride) * output_stride + 1)


def to_input_resolution_height_and_width(internal_resolution, output_stride, input_resolution):
    input_height, input_width = input_resolution
    return (to_valid_input_resolution(input_height * internal_resolution, output_stride),
            to_valid_input_resolution(input_width * internal_resolution, output_stride))


def to_mask_tensor(segment_scores, threshold):
    _, thresh = cv2.threshold(segment_scores, threshold, 1, cv2.THRESH_BINARY)
    return thresh
