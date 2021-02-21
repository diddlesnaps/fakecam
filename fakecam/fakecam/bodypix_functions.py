import cv2
import numpy as np


class BodypixScaler:
    width = 0
    height = 0
    zeroes = None
    ones = None
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.zeroes = cv2.UMat(np.zeros((height, width)))
        self.ones = cv2.UMat(np.ones((height, width)))


    def remove_padding_and_resize_back(self, resized_and_padded):
        return cv2.resize(resized_and_padded, (self.width, self.height))


    def sigmoid(self, x):
        subbed = cv2.subtract(self.zeroes, x, dtype=cv2.CV_32F)
        added = cv2.add(self.ones, cv2.exp(subbed), dtype=cv2.CV_32F)
        return cv2.divide(self.ones, added, dtype=cv2.CV_32F)


    def scale_and_crop_to_input_tensor_shape(self, tensor,
                                            apply_sigmoid_activation):
        in_resized_and_padded = cv2.resize(tensor,
                                           (self.width, self.height))
        if apply_sigmoid_activation:
            in_resized_and_padded = self.sigmoid(in_resized_and_padded)

        return self.remove_padding_and_resize_back(in_resized_and_padded)


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
