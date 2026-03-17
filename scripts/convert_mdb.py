import os
import pandas as pd
from pathlib import Path

def convert_csvs_to_parquet(source_dir: str, target_dir: str):
    source_path = Path(source_dir)
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    
    csv_files = list(source_path.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files in {source_dir}")
    
    for csv_file in csv_files:
        table_name = csv_file.stem
        parquet_file = target_path / f"{table_name}.parquet"
        
        try:
            # We use low_memory=False because we don't know the schema and files are small
            df = pd.read_csv(csv_file, low_memory=False)
            
            # Basic cleanup: some MDB exports might have empty strings or weird nulls
            # For data consistency, we'll strip strings if any
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].astype(str).str.strip()
            
            df.to_parquet(parquet_file, engine='pyarrow', index=False)
            print(f"Converted {table_name} -> {parquet_file.name}")
        except Exception as e:
            print(f"Error converting {table_name}: {e}")

if __name__ == "__main__":
    convert_csvs_to_parquet("/tmp/kc_dual_csv", "src/simdualkc/data")
