import pandas as pd
from typing import List
from pathlib import Path

dataFolder = '/work/pi_plunkett_umass_edu/bcu/data/processed/osm'

def combine_csv_for_town(file_list: List[str], output_filename: str, region: str) -> None:
    """
    Combines the destinations (of all types) for a town into 1 main csv file.
    """
    # Read each CSV file into a list of DataFrames
    df_list = [pd.read_csv(f'{dataFolder}/{file}') for file in file_list]
    
    # Concatenate all DataFrames together vertically
    combined_df = pd.concat(df_list, ignore_index=True)

    # Add the new 'town' column and assign it the region value for all rows
    combined_df['town'] = region
    
    # Save the massive combined DataFrame to a new CSV file
    csv_output_path = Path(dataFolder) / f'{output_filename}'
    combined_df.to_csv(csv_output_path, index=False)
    print(f"Successfully combined {len(file_list)} files into {output_filename}")

def combine_csvs(file_list: List[str], output_filename: str) -> None:
    """
    Combines all destinations into 1 master csv.
    """
    # Read each CSV file into a list of DataFrames
    df_list = [pd.read_csv(f'{dataFolder}/{file}') for file in file_list]
    
    # Concatenate all DataFrames together vertically
    combined_df = pd.concat(df_list, ignore_index=True)
    
    # Save the massive combined DataFrame to a new CSV file
    csv_output_path = Path(dataFolder) / f'{output_filename}'
    combined_df.to_csv(csv_output_path, index=False)
    print(f"Successfully combined {len(file_list)} files into {output_filename}")

if __name__ == '__main__':
    combine_csv_for_town(["BostonGreenspace_Coordinates.csv", "BostonHealthcare_Coordinates.csv","BostonSchool_Coordinates.csv","BostonStore_Coordinates.csv","BostonTransitStation_Coordinates.csv"], "BostonDestinations.csv", "Boston")
    combine_csv_for_town(["BrooklineGreenspace_Coordinates.csv", "BrooklineHealthcare_Coordinates.csv","BrooklineSchool_Coordinates.csv","BrooklineStore_Coordinates.csv","BrooklineTransitStation_Coordinates.csv"], "BrooklineDestinations.csv", "Brookline")
    combine_csv_for_town(["CambridgeGreenspace_Coordinates.csv", "CambridgeHealthcare_Coordinates.csv","CambridgeSchool_Coordinates.csv","CambridgeStore_Coordinates.csv","CambridgeTransitStation_Coordinates.csv"], "CambridgeDestinations.csv", "Cambridge")
    combine_csv_for_town(["SomervilleGreenspace_Coordinates.csv", "SomervilleHealthcare_Coordinates.csv","SomervilleSchool_Coordinates.csv","SomervilleStore_Coordinates.csv","SomervilleTransitStation_Coordinates.csv"], "SomervilleDestinations.csv", "Somerville")
    combine_csvs(["BostonDestinations.csv","BrooklineDestinations.csv","CambridgeDestinations.csv","SomervilleDestinations.csv"], "Destinations.csv")