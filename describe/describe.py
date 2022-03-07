# Generated by nuclio.export.NuclioExporter

import warnings

import mlrun.artifacts

warnings.simplefilter(action="ignore", category=FutureWarning)

import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
from mlrun.artifacts import PlotlyArtifact, TableArtifact
from mlrun.datastore import DataItem
from mlrun.execution import MLClientCtx
from plotly.subplots import make_subplots

pd.set_option("display.float_format", lambda x: "%.2f" % x)
MAX_SIZE_OF_DF = 5000


def analysis(
    context: MLClientCtx,
    name: str = "dataset",
    table: DataItem = None,
    label_column: str = None,
    plots_dest: str = "plots",
    update_dataset: bool = False,
    frac: float = 0.10,
) -> None:
    """
    The function will output the following artifacts per
    column within the data frame (based on data types):

    histogram matrix chart
    histogram per feature chart
    violin chart
    correlation-matrix chart
    correlation-matrix csv
    imbalance pie chart
    imbalance-weights-vec csv

    :param context:                 the function context
    :param name:                    key of dataset to database ("dataset" for default)
    :param table:                   MLRun input pointing to pandas dataframe (csv/parquet file path)
    :param label_column:            ground truth column label
    :param plots_dest:              destination folder of summary plots (relative to artifact_path)
                                    ("plots" for default)
    :param update_dataset:          when the table is a registered dataset update the charts in-place
    :param frac:                    when the table has more than 5000 samples,
                                    the function will execute on random frac from the data (0.1 default)
    """

    df = table.as_df()
    if df.shape[0] > MAX_SIZE_OF_DF:
        df = df.sample(frac=frac)
    extra_data = {}

    _create_histogram_mat_artifact(
        context, df, extra_data, label_column, plots_dest
    )
    _create_features_histogram_artifacts(
        context, df, extra_data, label_column, plots_dest
    )
    _create_violin_artifact(
        context, df, extra_data, plots_dest
                            )
    _create_imbalance_artifact(
        context, df, extra_data, label_column, plots_dest
                               )
    _create_corr_artifact(
        context, df, extra_data, label_column, plots_dest
                          )

    artifact = table._artifact_url
    if artifact is None:  # dataset not stored
        artifact = context.log_dataset(key="dataset", db_key=name, stats=True, df=df)

    if update_dataset:
        from mlrun.artifacts import update_dataset_meta

        update_dataset_meta(artifact, extra_data=extra_data)

    # TODO : Plots according to client wishes - like preform histogram on selected features.
    # TODO : 3-D plot on on selected features.
    # TODO : Reintegration plot on on selected features.


def _create_histogram_mat_artifact(
    context: MLClientCtx,
    df: pd.DataFrame,
    extra_data: dict,
    label_column: str,
    plots_dest: str,
):
    """
    Create and log a histogram matrix artifact
    """
    try:
        df_new = df.copy()
        df_new[label_column] = df_new[label_column].apply(str)
        fig = ff.create_scatterplotmatrix(
            df_new, diag="histogram", index=label_column, width=2500, height=2500
        )
        fig.update_layout(title_text="<i><b>Histograms matrix</b></i>")
        extra_data["histogram matrix"] = context.log_artifact(
            PlotlyArtifact(key="histograms matrix", figure=fig),
            local_path=f"{plots_dest}/hist_mat.html",
        )
    except Exception as e:
        context.logger.error(f"Failed to create histogram matrix artifact due to: {e}")


def _create_features_histogram_artifacts(
    context: MLClientCtx,
    df: pd.DataFrame,
    extra_data: dict,
    label_column: str,
    plots_dest: str,
):
    """
    Create and log a histogram artifact for each feature
    """
    try:
        for (columnName, _) in df.iteritems():
            if columnName == label_column:
                continue
            fig = px.histogram(
                df,
                x=columnName,
                color=label_column,
                marginal="box",
                hover_data=df.columns,
            )

            fig.update_layout(title_text=f"<i><b>Histograms {columnName}</b></i>")
            extra_data[f"histogram_{columnName}"] = context.log_artifact(
                PlotlyArtifact(key=f"histogram_{columnName}", figure=fig),
                local_path=f"{plots_dest}/hist_{columnName}.html",
            )
    except Exception as e:
        context.logger.error(f"Failed to create pairplot histograms due to: {e}")


def _create_violin_artifact(
    context: MLClientCtx, df: pd.DataFrame, extra_data: dict, plots_dest: str
):
    """
    Create and log a violin artifact
    """
    try:
        fig = make_subplots(rows=(df.shape[1] // 3) + 1, cols=3)
        i = 0
        for (columnName, columnData) in df.iteritems():
            fig.add_trace(
                go.Violin(
                    x=[columnName] * columnData.shape[0],
                    y=columnData,
                    name=columnName,
                    # box_visible=True,
                    # meanline_visible=True
                ),
                row=(i // 3) + 1,
                col=(i % 3) + 1,
            )
            i += 1

        fig.update_layout(title_text="<i><b>Violin Plots</b></i>")
        extra_data["violin"] = context.log_artifact(
            PlotlyArtifact(key="violin", figure=fig),
            local_path=f"{plots_dest}/violin.html",
        )
    except Exception as e:
        context.logger.warn(f"Failed to create violin distribution plots due to: {e}")


def _create_imbalance_artifact(
    context: MLClientCtx,
    df: pd.DataFrame,
    extra_data: dict,
    label_column: str,
    plots_dest: str,
):
    """
    Create and log an imbalance class artifact (csv + plot)
    """
    if label_column:
        labels_count = df[label_column].value_counts().sort_index()
        df_labels_count = pd.DataFrame(labels_count)
        df_labels_count.rename(columns={label_column: "Total"}, inplace=True)
        df_labels_count[label_column] = labels_count.index
        try:
            fig = px.pie(df_labels_count, names=label_column, values="Total")
            fig.update_layout(title_text="<i><b>Labels balance</b></i>")
            extra_data["imbalance"] = context.log_artifact(
                PlotlyArtifact(key="imbalance", figure=fig),
                local_path=f"{plots_dest}/imbalance.html",
            )
        except Exception as e:
            context.logger.warn(f"Failed to create class imbalance plot due to: {e}")
        extra_data["imbalance csv"] = context.log_artifact(
            TableArtifact(
                "imbalance-weights-vec", df=pd.DataFrame({"weights": labels_count})
            ),
            local_path=f"{plots_dest}/imbalance-weights-vec.csv",
        )


def _create_corr_artifact(
    context: MLClientCtx,
    df: pd.DataFrame,
    extra_data: dict,
    label_column: str,
    plots_dest: str,
):
    """
    Create and log an correlation-matrix artifact (csv + plot)
    """
    df.drop([label_column], axis=1, inplace=True)
    tblcorr = df.corr()
    extra_data["correlation-matrix csv"] = context.log_artifact(
        TableArtifact("correlation-matrix csv", df=tblcorr, visible=True),
        local_path=f"{plots_dest}/correlation-matrix.csv",
    )

    try:
        z = tblcorr.values.tolist()
        z_text = [["{:.2f}".format(y) for y in x] for x in z]
        fig = ff.create_annotated_heatmap(
            z,
            x=list(df.columns),
            y=list(df.columns),
            annotation_text=z_text,
            colorscale="agsunset",
        )
        fig["layout"]["yaxis"]["autorange"] = "reversed"  # l -> r
        fig.update_layout(title_text="<i><b>Correlation matrix</b></i>")
        fig["data"][0]["showscale"] = True

        extra_data["correlation-matrix"] = context.log_artifact(
            PlotlyArtifact(key="correlation-matrix", figure=fig),
            local_path=f"{plots_dest}/corr.html",
        )
    except Exception as e:
        context.logger.warn(f"Failed to create features correlation plot due to: {e}")
