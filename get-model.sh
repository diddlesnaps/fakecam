#!/bin/sh

MODEL_DIR=bodypix_mobilenet_float_050_model-stride16
OUTPUTS=float_segments

mkdir $MODEL_DIR
curl -o $MODEL_DIR/model.json https://storage.googleapis.com/tfjs-models/savedmodel/bodypix/mobilenet/float/050/model-stride16.json
curl -o $MODEL_DIR/group1-shard1of1.bin https://storage.googleapis.com/tfjs-models/savedmodel/bodypix/mobilenet/float/050/group1-shard1of1.bin

docker build -t tfjs-to-tf https://raw.githubusercontent.com/patlevin/tfjs-to-tf/master/docker/Dockerfile 
docker run --rm -u $(id -u):$(id -g) -v $PWD:$PWD -w $PWD tfjs-to-tf \
    --output_format tf_saved_model \
    --outputs $OUTPUTS \
    $MODEL_DIR $MODEL_DIR/tf_saved_model
docker run --rm -u $(id -u):$(id -g) -v $PWD:$PWD -w $PWD tensorflow/tensorflow \
    python3 /usr/local/lib/python3.6/dist-packages/tensorflow/python/tools/freeze_graph.py \
    --input_saved_model_dir $MODEL_DIR/tf_saved_model \
    --output_graph $MODEL_DIR/frozen_graph.pb \
    --output_node_names $OUTPUTS
