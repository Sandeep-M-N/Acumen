import os
import pandas as pd
import pyreadstat
from datetime import datetime
from openpyxl import load_workbook

def convert_sas_to_excel(input_folder, output_folder):
    """
    Robust SAS to Excel converter that handles encoding issues
    """
    os.makedirs(output_folder, exist_ok=True)
    row_counts = []
    error_log = []
    
    for file in sorted(os.listdir(input_folder)):
        if not file.lower().endswith('.sas7bdat'):
            continue
            
        file_path = os.path.join(input_folder, file)
        excel_path = os.path.join(output_folder, f"{os.path.splitext(file)[0]}.xlsx")
        log_entry = {
            'dataset': os.path.splitext(file)[0],
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'FAILED',
            'row_count': 0,
            'error': None
        }
        
        try:
            # Try reading with pyreadstat first
            df, meta = pyreadstat.read_sas7bdat(file_path, encoding='latin1')
            row_count = len(df)
            
            # Handle potential encoding issues in column names
            df.columns = [str(col).encode('latin1').decode('utf-8', errors='replace') 
                         if isinstance(col, bytes) else str(col) for col in df.columns]
            
            # Save to Excel
            df.to_excel(excel_path, index=False, engine='openpyxl')
            
            log_entry.update({
                'status': 'SUCCESS',
                'row_count': row_count,
                'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            print(f"✓ Converted {file} ({row_count:,} rows)")
            
        except Exception as e:
            error_msg = str(e)
            if isinstance(e, bytes):
                error_msg = e.decode('latin1', errors='replace')
                
            log_entry.update({
                'error': error_msg,
                'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            print(f"✗ Failed {file}: {error_msg}")
            
        finally:
            row_counts.append(log_entry)
    
    # Create detailed log file
    log_df = pd.DataFrame(row_counts)
    log_path = os.path.join(output_folder, "conversion_log.csv")
    log_df.to_csv(log_path, index=False)
    
    return log_df

def analyze_excel_files(root_folder):
    """
    Analyze all Excel files in a folder and subfolders
    """
    results = []
    
    # Walk through all directories and files
    for foldername, subfolders, filenames in os.walk(root_folder):
        for filename in filenames:
            # Check if file is Excel file
            if filename.endswith(('.xlsx', '.xls')):
                filepath = os.path.join(foldername, filename)
                try:
                    # Try reading with pandas first (faster for most cases)
                    try:
                        df = pd.read_excel(filepath, nrows=0)  # Only read header
                        column_count = len(df.columns)
                        columns = list(df.columns)
                    except:
                        # Fallback to openpyxl if pandas fails
                        wb = load_workbook(filepath, read_only=True)
                        sheet = wb.active
                        columns = [cell.value for cell in sheet[1]]  # First row
                        column_count = len(columns)
                        wb.close()
                    
                    results.append({
                        'file_path': filepath,
                        'column_count': column_count,
                        'columns': columns
                    })
                    
                except Exception as e:
                    results.append({
                        'file_path': filepath,
                        'error': str(e)
                    })
    
    return results

def print_analysis_results(results):
    """
    Print the analysis results in a readable format
    """
    for result in results:
        print("\n" + "="*80)
        print(f"File: {result['file_path']}")
        
        if 'error' in result:
            print(f"Error: {result['error']}")
            continue
            
        print(f"Number of columns: {result['column_count']}")
        print("Columns:")
        for i, col in enumerate(result['columns'], 1):
            print(f"{i}. {col}")

def main():
    # Configuration - Update these paths
    config = {
        'base_path': r"path_of_the_folder",
        'output_folder': 'sas_excel_output',
        'folders': {
            'ADAM': os.path.join('ADAM', 'ADAM'),
            'SDTM': os.path.join('SDTM', 'SDTM')
        }
    }
    
    # Prepare output structure
    os.makedirs(config['output_folder'], exist_ok=True)
    results = []
    
    # Process each domain
    for domain, rel_path in config['folders'].items():
        input_path = os.path.join(config['base_path'], rel_path)
        output_path = os.path.join(config['output_folder'], f"{domain.lower()}_excel")
        
        if not os.path.exists(input_path):
            print(f"⚠ Warning: {domain} folder not found at {input_path}")
            continue
            
        print(f"\n{'='*40}")
        print(f"Processing {domain} files")
        print(f"{'='*40}")
        
        domain_results = convert_sas_to_excel(input_path, output_path)
        domain_results['domain'] = domain
        results.append(domain_results)
    
    # Generate final conversion report
    if results:
        final_report = pd.concat(results)
        report_path = os.path.join(config['output_folder'], "final_conversion_report.csv")
        final_report.to_csv(report_path, index=False)
        
        # Print conversion summary
        success = final_report[final_report['status'] == 'SUCCESS']
        failed = final_report[final_report['status'] == 'FAILED']
        
        print("\n\n=== CONVERSION SUMMARY ===")
        print(f"Total files processed: {len(final_report)}")
        print(f"Successfully converted: {len(success)}")
        print(f"Failed conversions: {len(failed)}")
        print(f"\nTotal rows processed: {success['row_count'].sum():,}")
        
        if not failed.empty:
            print("\nFailed files:")
            for _, row in failed.iterrows():
                print(f"- {row['dataset']}: {row['error']}")
        
        print(f"\nDetailed report saved to: {report_path}")
    
    # Analyze the converted Excel files
    print("\n\n=== ANALYZING CONVERTED EXCEL FILES ===")
    analysis_results = analyze_excel_files(config['output_folder'])
    print_analysis_results(analysis_results)
    
    # Save analysis results to CSV
    df_results = pd.DataFrame([r for r in analysis_results if 'error' not in r])
    if not df_results.empty:
        output_file = os.path.join(config['output_folder'], 'excel_columns_analysis.csv')
        df_results.to_csv(output_file, index=False)
        print(f"\nAnalysis results saved to: {output_file}")

if __name__ == "__main__":
    main()