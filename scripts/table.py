import json
import pandas as pd
import geopandas as gpd
import util as u

from shapely.geometry import Point
from pathlib import Path, PurePath

# Column field name variables
# Before running this script, update the variables with the strings matching
# the names in the dataset for csduid column, index, lat, and long columns.
TABLECONFIG = "./source/Tables/ODI/odi.json"
CSDUID = "csduid"
INDEX = "id"
LAT = None
LONG = None


def BuildDf(iFile):
    """
    Build a Data Frame with the provided dataset
    :param iFile {string} - Path to input dataset
    :return pandas dataframe
    """
    df = pd.read_csv(iFile, index_col=False, encoding='utf-8', dtype={CSDUID: str})

    # Exclude null lat/long series from data frame
    if LAT is not None and LONG is not None:
        df = df[~df[LAT].isnull()][~df[LONG].isnull()]

    return df


def UpdateDFColOrder(df, config_cols):
    """
    Update the column order of the data frame to match the order of the columns listed in the config
    :param df: Pandas dataframe
    :param config_cols: table config file property containing a list of fields
    :return: Updated data frame
    """

    df_columns_updated = []
    df_columns = df.columns.to_list()

    for config_col in config_cols:
        config_col_id = config_col['id']
        if config_col_id in df_columns:
            # Append config column
            df_columns_updated.append(config_col_id)

            # Remove matching column from df column list
            df_columns.remove(config_col_id)

    # Add remaining df columns to updated columns list
    df_columns_updated.extend(df_columns)

    # Update df column order
    df = df[df_columns_updated]

    return df


def CreateTableConfig(path, config):
    """
    Create the table config file and stores it in ./output/config/tables directory
    :param path {string} -
    :param config {dictionary} - table configuration used to generate tables
    """
    jPath = PurePath("./data", path)
    cPath = PurePath("./output", "./config", "./tables")

    Path(cPath).mkdir(parents=True, exist_ok=True)

    del config["source"]

    config["path"] = str(jPath)

    file = 'config.table.' + path.lower() + ".json"

    u.DumpJSON(cPath.joinpath(file), config)


def CreateTableFiles(df, path, drop, config):
    """
    Create table files from data, and also the associated table config file
    :param df {dataframe} - dataframe containing input data
    :param path {string} - The ID of data being processed which is used to specify the output of the table files
    :param drop {list} - a list of drop columns which were not used included in the output
    :param config {dictionary} - configuration of how to generate the table output files
    """
    # Create the string for the path for storing output data.
    tPath = PurePath("./output", "./data", path)

    # Create the output data directory
    Path(tPath).mkdir(parents=True, exist_ok=True)

    # Split dataframe content by CSD Unique ID
    csduid_groups = df.groupby(CSDUID)

    # Loops through each csduid (x) in the groups and copies the associated csduid df (y) into the split list
    split = [pd.DataFrame(y) for x, y in csduid_groups]

    config["summary"] = {}

    # Loop through split dataframe content and output it's content as csv files
    # Note: CSV files represent features in specific CSD's and are grouped by 50 records
    for s in split:
        CSD = str(s[CSDUID].iloc[0])
        s = s.sort_values(INDEX, ascending=True).drop(columns=drop)

        # Break-up split CSD content into groups of 50 for each page of the table view
        # Note: This commonly occurs for higher density urban areas.
        split_50 = [s[i:i + 49] for i in range(0, len(s), 50)]

        if len(s) > 0:
            config["summary"][CSD] = len(split_50)

        for index, s_50 in enumerate(split_50):
            # Update output file name based on index of the 50 record group
            oFile = CSD + '_' + str(index + 1) + '.json'

            # Output CSV file with json extension because NDM server don't allow CSV files for some reason.
            u.DumpCSV(tPath.joinpath(oFile), s_50)

    # Create a table config file
    CreateTableConfig(path, config)


def CreateShapefile(df, oFile, drop):
    sPath = PurePath("./output", "./shp")

    Path(sPath).mkdir(parents=True, exist_ok=True)

    geometry = [Point(xy) for xy in zip(df[LONG], df[LAT])]

    gdf = gpd.GeoDataFrame(df.drop(columns=drop), dtype='str', crs={'init': 'epsg:4326'}, geometry=geometry)

    gdf.to_file(sPath.joinpath((oFile)), driver="ESRI Shapefile", index=True)


# Base table configuration, this needs to be changed by dataset
config = u.ReadJSON(TABLECONFIG)

# Create a dataframe based on data source URL provided in the config file
df = BuildDf(config["source"])

# Ensure CSDUID column is of type integer
csduid_df = df[CSDUID]
csduid_df = pd.to_numeric(csduid_df, downcast='integer')
df[CSDUID] = csduid_df

# Update column order of df to match fields order in config
df = UpdateDFColOrder(df, config["fields"])

# Create a list of dropped fields not listed in the table config file
drop = u.GetDropFields(df, config["fields"])

# Create table files for data based on boundary locations
CreateTableFiles(df, config["id"], drop, config)

# CreateShapefile(df, config["id"] + ".shp", drop)
