import os
import shutil
import tempfile

import mlrun

# Choose our model's name:
MODEL_NAME = "model"

# Choose our ONNX version model's name:
ONNX_MODEL_NAME = f"onnx_{MODEL_NAME}"

# Choose our optimized ONNX version model's name:
OPTIMIZED_ONNX_MODEL_NAME = f"optimized_{ONNX_MODEL_NAME}"


def _setup_environment() -> str:
    """
    Setup the test environment, creating the artifacts path of the test.

    :returns: The temporary directory created for the test artifacts path.
    """
    artifact_path = tempfile.TemporaryDirectory().name
    os.makedirs(artifact_path)
    return artifact_path


def _cleanup_environment(artifact_path: str):
    """
    Cleanup the test environment, deleting files and artifacts created during the test.

    :param artifact_path: The artifact path to delete.
    """
    # Clean the local directory:
    for test_output in [
        *os.listdir(artifact_path),
        "schedules",
        "runs",
        "artifacts",
        "functions",
    ]:
        test_output_path = os.path.abspath(f"./{test_output}")
        if os.path.exists(test_output_path):
            if os.path.isdir(test_output_path):
                shutil.rmtree(test_output_path)
            else:
                os.remove(test_output_path)

    # Clean the artifacts directory:
    shutil.rmtree(artifact_path)


def _log_tf_keras_model(context: mlrun.MLClientCtx, model_name: str):
    """
    Create and log a tf.keras model - MobileNetV2.

    :param context:    The context to log to.
    :param model_name: The model name to use.
    """
    import mlrun.frameworks.tf_keras as mlrun_tf_keras
    from tensorflow import keras

    # Download the MobileNetV2 model:
    model = keras.applications.mobilenet_v2.MobileNetV2()

    # Initialize a model handler for logging the model:
    model_handler = mlrun_tf_keras.TFKerasModelHandler(
        model_name=model_name, model=model, context=context
    )

    # Log the model:
    model_handler.log()


def _log_onnx_model(context: mlrun.MLClientCtx, model_name: str):
    """
    Create and log an ONNX model - MNIST.

    :param context:    The context to log to.
    :param model_name: The model name to use.
    """
    import mlrun.frameworks.onnx as mlrun_onnx
    import requests

    # Download the MNIST model:
    mnist_model_name = "mnist-8"
    requested_model = requests.get(
        f"https://github.com/onnx/models/blob/master/vision/classification/mnist/"
        f"model/{mnist_model_name}.onnx?raw=true"
    )
    with open(
        os.path.join(context.artifact_path, f"{model_name}.onnx"), "bw"
    ) as onnx_file:
        onnx_file.write(requested_model.content)

    # Initialize a model handler for logging the model:
    model_handler = mlrun_onnx.ONNXModelHandler(
        model_name=model_name,
        model_path=context.artifact_path,
        context=context,
    )
    model_handler.load()

    # Log the model:
    model_handler.log()


def test_tf_keras_to_onnx():
    """
    Test the 'to_onnx' handler, giving it a tf.keras model.
    """
    # Setup the tests environment:
    artifact_path = _setup_environment()

    # Create the function parsing this notebook's code using 'code_to_function':
    log_model_function = mlrun.code_to_function(
        filename="test_mlrun_onnx.py",
        name="log_model",
        kind="job",
        image="mlrun/ml-models",
    )

    # Run the function to log the model:
    log_model_run = log_model_function.run(
        handler="_log_tf_keras_model",
        artifact_path=artifact_path,
        params={"model_name": MODEL_NAME},
        local=True,
    )

    # Import the ONNX function from the marketplace:
    onnx_function = mlrun.import_function("function.yaml")

    # Run the function to convert our model to ONNX:
    onnx_function.run(
        handler="to_onnx",
        artifact_path=artifact_path,
        params={
            "model_name": MODEL_NAME,
            "model_path": log_model_run.outputs[
                MODEL_NAME
            ],  # <- Take the logged model from the previous function.
            "onnx_model_name": ONNX_MODEL_NAME,
        },
        local=True,
    )

    # Get the artifacts list:
    artifacts_list = os.listdir(artifact_path)
    print(f"Produced artifacts: {artifacts_list}")

    # Cleanup the tests environment:
    _cleanup_environment(artifact_path=artifact_path)

    # Verify the '.onnx' model was created:
    assert "{}.onnx".format(ONNX_MODEL_NAME) in artifacts_list


def test_optimize():
    """
    Test the 'optimize' handler, giving it a model from the ONNX zoo git repository.
    """
    # Setup the tests environment:
    artifact_path = _setup_environment()

    # Create the function parsing this notebook's code using 'code_to_function':
    log_model_function = mlrun.code_to_function(
        filename="test_mlrun_onnx.py",
        name="log_model",
        kind="job",
        image="mlrun/ml-models",
    )

    # Run the function to log the model:
    log_model_run = log_model_function.run(
        handler="_log_onnx_model",
        artifact_path=artifact_path,
        params={"model_name": MODEL_NAME},
        local=True,
    )

    # Import the ONNX function from the marketplace:
    onnx_function = mlrun.import_function("function.yaml")

    # Run the function to convert our model to ONNX:
    onnx_function.run(
        handler="optimize",
        artifact_path=artifact_path,
        params={
            "model_name": MODEL_NAME,
            "model_path": log_model_run.outputs[
                MODEL_NAME
            ],  # <- Take the logged model from the previous function.
            "optimized_model_name": OPTIMIZED_ONNX_MODEL_NAME,
        },
        local=True,
    )

    # Get the artifacts list:
    artifacts_list = os.listdir(artifact_path)
    print(f"Produced artifacts: {artifacts_list}")

    # Cleanup the tests environment:
    _cleanup_environment(artifact_path=artifact_path)

    # Verify the '.onnx' model was created:
    assert "{}.onnx".format(OPTIMIZED_ONNX_MODEL_NAME) in artifacts_list
