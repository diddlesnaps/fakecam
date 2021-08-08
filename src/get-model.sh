#!/bin/bash

RESNET50_BASE_URL="https://storage.googleapis.com/tfjs-models/savedmodel/bodypix/resnet50/"
MOBILENET_BASE_URL="https://storage.googleapis.com/tfjs-models/savedmodel/bodypix/mobilenet/"

VALID_RESNET_STRIDES=("16" "32")
VALID_RESNET_MULTIPLIERS=("100")

VALID_MOBILENET_STRIDES=("8" "16")
VALID_MOBILENET_MULTIPLIERS=("050" "075" "100")

VALID_QUANT_BYTES=("1" "2" "4")

OUTPUTS="float_segments"

resNetSavedModel() {
    stride="$1"
    quantBytes="$2"

    graphJson="model-stride${stride}.json"

    if [ "$quantBytes" = "4" ]; then
        echo "${RESNET50_BASE_URL}float/${graphJson}"
    else
        echo "${RESNET50_BASE_URL}quant${quantBytes}/${graphJson}"
    fi
}

mobileNetSavedModel() {
    stride="$1"
    multiplier="$2"
    quantBytes="$3"

    graphJson="model-stride${stride}.json"
    if [ "$quantBytes" = "4" ]; then
        echo "${MOBILENET_BASE_URL}float/${multiplier}/${graphJson}"
    else
        echo "${MOBILENET_BASE_URL}quant${quantBytes}/${multiplier}/${graphJson}"
    fi
}

docker build -t tfjs-to-tf https://raw.githubusercontent.com/patlevin/tfjs-to-tf/master/docker/Dockerfile 

for MODEL_TYPE in "mobileNet" "resNet"; do

    case "$MODEL_TYPE" in
        "resNet")
            VALID_STRIDES="${VALID_RESNET_STRIDES[@]}"
            VALID_MULTIPLIERS="${VALID_RESNET_MULTIPLIERS[@]}"
            ;;
        "mobileNet")
            VALID_STRIDES="${VALID_MOBILENET_STRIDES[@]}"
            VALID_MULTIPLIERS="${VALID_MOBILENET_MULTIPLIERS[@]}"
            ;;
        *)
            exit 1
    esac

    for STRIDE in $VALID_STRIDES; do
        
        for MULTIPLIER in $VALID_MULTIPLIERS; do

            for QUANT_BYTES in "${VALID_QUANT_BYTES[@]}"; do

                MODEL_DIR="$(dirname $0)/fakecam/$MODEL_TYPE/$STRIDE/$MULTIPLIER/$QUANT_BYTES"
                MODEL_PATH="$MODEL_DIR/model.json"

                mkdir -p "$MODEL_DIR"

                case "$MODEL_TYPE" in
                    "resNet")
                        URL="$(resNetSavedModel "$STRIDE" "$QUANT_BYTES")"
                        ;;
                    "mobileNet")
                        URL="$(mobileNetSavedModel "$STRIDE" "$MULTIPLIER" "$QUANT_BYTES")"
                        ;;
                esac

                curl -so "$MODEL_PATH" "$URL"

                WEIGHTS=$(cat "$MODEL_PATH" | jq -r '.weightsManifest[].paths[]')

                for WEIGHT in $WEIGHTS; do

                    curl -so "$MODEL_DIR/$WEIGHT" "$(dirname "$URL")/$WEIGHT"
                
                done

                echo "$MODEL_DIR"
                docker run --rm -u $(id -u):$(id -g) -v "$PWD:$PWD" -w "$PWD" tfjs-to-tf \
                    --output_format tf_saved_model \
                    --outputs "$OUTPUTS" \
                    "$MODEL_DIR" "$MODEL_DIR/tf_saved_model"
                
                docker run --rm -u $(id -u):$(id -g) -v "$PWD:$PWD" -w "$PWD" tensorflow/tensorflow \
                    python3 /usr/local/lib/python3.6/dist-packages/tensorflow/python/tools/freeze_graph.py \
                    --input_saved_model_dir "$MODEL_DIR/tf_saved_model" \
                    --output_graph "$MODEL_DIR/frozen_graph.pb" \
                    --output_node_names "$OUTPUTS"
        
            done

        done

    done

done
