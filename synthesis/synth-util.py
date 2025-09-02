#!/usr/bin/env python3
"""
Synthesis Utility for comparing CIRCT and Yosys+ABC synthesis flows.

This utility provides functions to:
1. Run CIRCT synthesis pipeline
2. Run Yosys+ABC synthesis pipeline  
3. Compare the results between the two flows

Usage:
    python synth-util.py input.sv
    python synth-util.py --lut-k 4 input.v
    python synth-util.py --output-dir results --verbose input.sv
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, List
import tempfile
import shutil
import glob


class SynthesisResults:
    """Container for synthesis results from either flow."""
    
    def __init__(self):
        self.timing_levels: Optional[int] = None
        self.lut_count: Optional[int] = None
        self.runtime: Optional[float] = None
        self.success: bool = False
        self.error_message: Optional[str] = None
        
    def __repr__(self):
        return f"SynthesisResults(levels={self.timing_levels}, luts={self.lut_count}, runtime={self.runtime:.3f}s, success={self.success})"


class SynthesisComparator:
    """Main class for running and comparing synthesis flows."""
    
    def __init__(self, lut_k: int = 6, output_dir: str = "build", verbose: bool = False):
        self.lut_k = lut_k
        self.output_dir = Path(output_dir)
        self.verbose = verbose
        
        # Create output directories
        self.circt_dir = self.output_dir / "circt"
        self.yosys_dir = self.output_dir / "yosys-abc"
        self.circt_dir.mkdir(parents=True, exist_ok=True)
        self.yosys_dir.mkdir(parents=True, exist_ok=True)
        
    def log(self, message: str):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(f"[DEBUG] {message}")
            
    def run_command(self, cmd: list, cwd: Optional[str] = None, capture_output: bool = True) -> Tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        self.log(f"Running: {' '.join(cmd)}")
        if cwd:
            self.log(f"Working directory: {cwd}")
            
        try:
            if capture_output:
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
                if result.stderr and (result.returncode != 0 or self.verbose):
                    self.log(f"Command stderr: {result.stderr}")
                return result.returncode, result.stdout, result.stderr
            else:
                result = subprocess.run(cmd, cwd=cwd)
                return result.returncode, "", ""
        except FileNotFoundError as e:
            error_msg = f"Command not found: {e}"
            self.log(error_msg)
            return -1, "", error_msg
        except Exception as e:
            error_msg = f"Error running command: {e}"
            self.log(error_msg)
            return -1, "", error_msg
    
    def run_circt_synthesis(self, input_file: str) -> SynthesisResults:
        """Run CIRCT synthesis pipeline."""
        import time
        
        results = SynthesisResults()
        file_base = Path(input_file).stem
        
        # Define output files
        mlir_file = self.circt_dir / f"{file_base}.mlir"
        synth_file = self.circt_dir / f"{file_base}.synth.mlir"
        json_file = self.circt_dir / f"{file_base}.longest_path.json"
        
        start_time = time.time()
        
        try:
            # Step 1: Convert Verilog to MLIR
            print("Converting SystemVerilog to MLIR...")
            cmd = ["circt-verilog", input_file, "-o", str(mlir_file), "--mlir-timing"]
            returncode, stdout, stderr = self.run_command(cmd)
            
            if self.verbose and stdout:
                self.log(f"circt-verilog stdout: {stdout}")
            if stderr:
                self.log(f"circt-verilog stderr: {stderr}")
            
            if returncode != 0:
                results.error_message = f"circt-verilog failed: {stderr}"
                return results
                
            # Step 2: Run CIRCT synthesis
            print(f"Running CIRCT synthesis with LUT-{self.lut_k}...")
            cmd = [
                "circt-synth", str(mlir_file),
                f"--lower-to-k-lut={self.lut_k}",
                "--output-longest-path-top-k-percent=0",
                f"--output-longest-path={json_file}",
                "--output-longest-path-json",
                "-o", str(synth_file),
                "--mlir-timing"
            ]
            
            returncode, stdout, stderr = self.run_command(cmd)
            
            if self.verbose and stdout:
                self.log(f"circt-synth stdout: {stdout}")
            if stderr:
                self.log(f"circt-synth stderr: {stderr}")
            
            if returncode != 0:
                results.error_message = f"circt-synth failed: {stderr}"
                return results
                
            # Step 3: Parse JSON results
            if json_file.exists():
                results.timing_levels, results.lut_count = self._parse_circt_json(json_file)
            else:
                self.log("Warning: JSON timing file not generated")
                
            results.runtime = time.time() - start_time
            results.success = True
            
        except Exception as e:
            results.error_message = f"CIRCT synthesis error: {e}"
            results.runtime = time.time() - start_time
            
        return results
    
    def run_yosys_synthesis(self, input_file: str) -> SynthesisResults:
        """Run Yosys+ABC synthesis pipeline."""
        import time
        
        results = SynthesisResults()
        file_base = Path(input_file).stem
        
        # Define output files
        aig_file = self.yosys_dir / f"{file_base}.aig"
        blif_file = self.yosys_dir / f"{file_base}.blif"
        log_file = self.yosys_dir / f"{file_base}.yosys.log"
        
        start_time = time.time()
        
        try:
            # Create Yosys script
            yosys_script = self._create_yosys_script(input_file, str(aig_file), str(blif_file))
            
            # Run Yosys
            print("Running Yosys synthesis...")
            cmd = ["yosys", "-s", yosys_script]
            returncode, stdout, stderr = self.run_command(cmd)
            
            # Log stderr for debugging
            if stderr:
                self.log(f"Yosys stderr: {stderr}")
            
            # Save log
            with open(log_file, 'w') as f:
                f.write(stdout)
                if stderr:
                    f.write(f"\n--- STDERR ---\n{stderr}")
            
            if returncode != 0:
                results.error_message = f"Yosys failed: {stderr}"
                return results
                
            # Parse results from log
            if log_file.exists():
                results.timing_levels = self._parse_yosys_abc_levels(log_file)
                
            # Count LUTs from BLIF file
            if blif_file.exists():
                results.lut_count = self._count_luts_in_blif(blif_file)
                
            results.runtime = time.time() - start_time
            results.success = True
            
            # Clean up temporary script
            os.unlink(yosys_script)
            
        except Exception as e:
            results.error_message = f"Yosys synthesis error: {e}"
            results.runtime = time.time() - start_time
            
        return results
    
    def run_hybrid_synthesis(self, input_file: str) -> SynthesisResults:
        """Run hybrid CIRCT front-end + Yosys back-end synthesis pipeline."""
        import time
        
        results = SynthesisResults()
        file_base = Path(input_file).stem
        
        # Define output files
        mlir_file = self.circt_dir / f"{file_base}.hybrid.mlir"
        synth_file = self.circt_dir / f"{file_base}.hybrid.synth.mlir"
        aig_file = self.circt_dir / f"{file_base}.hybrid.aig"
        blif_file = self.yosys_dir / f"{file_base}.hybrid.blif"
        log_file = self.yosys_dir / f"{file_base}.hybrid.log"
        
        start_time = time.time()
        
        try:
            # Step 1: Convert Verilog to MLIR using CIRCT
            print("Converting SystemVerilog to MLIR (CIRCT front-end)...")
            cmd = ["circt-verilog", input_file, "-o", str(mlir_file), "--mlir-timing"]
            returncode, stdout, stderr = self.run_command(cmd)
            
            if self.verbose and stdout:
                self.log(f"circt-verilog stdout: {stdout}")
            if stderr:
                self.log(f"circt-verilog stderr: {stderr}")
            
            if returncode != 0:
                results.error_message = f"circt-verilog failed: {stderr}"
                return results
                
            # Step 2: Run CIRCT synthesis (without LUT mapping)
            print("Running CIRCT synthesis (front-end only)...")
            cmd = [
                "circt-synth", str(mlir_file),
                "-o", str(synth_file),
                "--mlir-timing"
            ]
            
            returncode, stdout, stderr = self.run_command(cmd)
            
            if self.verbose and stdout:
                self.log(f"circt-synth stdout: {stdout}")
            if stderr:
                self.log(f"circt-synth stderr: {stderr}")
            
            if returncode != 0:
                results.error_message = f"circt-synth failed: {stderr}"
                return results
                
            # Step 3: Export to AIGER using circt-translate
            print("Exporting to AIGER format...")
            cmd = [
                "circt-translate", str(synth_file),
                "--export-aiger",
                "-o", str(aig_file)
            ]
            
            returncode, stdout, stderr = self.run_command(cmd)
            
            if self.verbose and stdout:
                self.log(f"circt-translate stdout: {stdout}")
            if stderr:
                self.log(f"circt-translate stderr: {stderr}")
            
            if returncode != 0:
                results.error_message = f"circt-translate AIGER export failed: {stderr}"
                return results
                
            # Step 4: Use Yosys to read AIGER and perform LUT mapping
            print("Running Yosys LUT mapping on CIRCT AIGER...")
            yosys_script = self._create_hybrid_yosys_script(str(aig_file), str(blif_file))
            
            cmd = ["yosys", "-s", yosys_script]
            returncode, stdout, stderr = self.run_command(cmd)
            
            # Log stderr for debugging
            if stderr:
                self.log(f"Yosys stderr: {stderr}")
            
            # Save log
            with open(log_file, 'w') as f:
                f.write(stdout)
                if stderr:
                    f.write(f"\n--- STDERR ---\n{stderr}")
            
            if returncode != 0:
                results.error_message = f"Yosys LUT mapping failed: {stderr}"
                return results
                
            # Parse results from log
            if log_file.exists():
                results.timing_levels = self._parse_yosys_abc_levels(log_file)
                
            # Count LUTs from BLIF file
            if blif_file.exists():
                results.lut_count = self._count_luts_in_blif(blif_file)
                
            results.runtime = time.time() - start_time
            results.success = True
            
            # Clean up temporary script
            os.unlink(yosys_script)
            
        except Exception as e:
            results.error_message = f"Hybrid synthesis error: {e}"
            results.runtime = time.time() - start_time
            
        return results
    
    def _create_yosys_script(self, input_file: str, aig_file: str, blif_file: str) -> str:
        """Create a temporary Yosys script for synthesis."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ys', delete=False) as f:
            f.write(f"""
# Yosys synthesis script for {input_file}
read_verilog -sv {input_file}
hierarchy -auto-top
synth
#abc -script +strash;,&get,-n;,&fraig,-x;,&put;,scorr;,dc2;,dretime;,strash;,dch,-f;,if,-K,{self.lut_k};,mfs2;,lutpack,{1};print_stats
abc -script +if,-K,{self.lut_k};,print_stats
#write_verilog foo.v
""")
            return f.name
    
    def _create_hybrid_yosys_script(self, aig_file: str, blif_file: str) -> str:
        """Create a temporary Yosys script for hybrid synthesis (AIGER input)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ys', delete=False) as f:
            f.write(f"""
# Hybrid Yosys script for CIRCT AIGER input: {aig_file}
read_aiger {aig_file}
# Simple ABC script focused on LUT mapping quality
abc -script +if,-K,{self.lut_k};print_stats
write_blif {blif_file}

""")
            return f.name
    
    def _parse_circt_json(self, json_file: Path) -> Tuple[Optional[int], Optional[int]]:
        """Parse CIRCT JSON timing output to extract levels and LUT count."""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                
            # Extract maximum timing level
            timing_levels = None
            lut_count = None
            
            if data and len(data) > 0 and 'timing_levels' in data[0]:
                levels_data = data[0]['timing_levels']
                if levels_data:
                    # Get maximum level
                    timing_levels = max(level['level'] for level in levels_data)
                    # Get count from 100% level (total LUTs)
                    for level in levels_data:
                        if level.get('percentage') == 100:
                            lut_count = level.get('count')
                            break
                            
            return timing_levels, lut_count
            
        except Exception as e:
            self.log(f"Error parsing CIRCT JSON: {e}")
            return None, None
    
    def _parse_yosys_abc_levels(self, log_file: Path) -> Optional[int]:
        """Parse Yosys log file to extract ABC logic levels."""
        try:
            with open(log_file, 'r') as f:
                content = f.read()
                
            # Look for ABC netlist statistics
            pattern = r'ABC: netlist\s*:\s*.*?\s+lev\s*=\s*(\d+)'
            matches = re.findall(pattern, content)
            
            if matches:
                # Take the last match (final result after optimization)
                return int(matches[-1])
                
            return None
            
        except Exception as e:
            self.log(f"Error parsing Yosys log: {e}")
            return None
    
    def _count_luts_in_blif(self, blif_file: Path) -> Optional[int]:
        """Count LUTs in BLIF file."""
        try:
            with open(blif_file, 'r') as f:
                content = f.read()
                
            # Count .names entries (LUTs)
            lut_count = len(re.findall(r'^\.names', content, re.MULTILINE))
            return lut_count if lut_count > 0 else None
            
        except Exception as e:
            self.log(f"Error counting LUTs in BLIF: {e}")
            return None
    
    def compare_results(self, circt_results: SynthesisResults, yosys_results: SynthesisResults, hybrid_results: Optional[SynthesisResults] = None) -> Dict[str, Any]:
        """Compare results from synthesis flows."""
        comparison = {
            'circt': circt_results,
            'yosys': yosys_results,
            'analysis': {}
        }
        
        if hybrid_results:
            comparison['hybrid'] = hybrid_results
        
        # Collect all successful results for comparison
        flows = []
        if circt_results.success:
            flows.append(('CIRCT', circt_results))
        if yosys_results.success:
            flows.append(('Yosys+ABC', yosys_results))
        if hybrid_results and hybrid_results.success:
            flows.append(('CIRCT+Yosys', hybrid_results))
        
        if len(flows) < 2:
            comparison['analysis']['timing_winner'] = 'Unable to compare'
            comparison['analysis']['area_winner'] = 'Unable to compare'
            return comparison
        
        # Timing levels comparison
        timing_levels = [(name, result.timing_levels) for name, result in flows if result.timing_levels is not None]
        if len(timing_levels) >= 2:
            timing_levels.sort(key=lambda x: x[1])  # Sort by levels (lower is better)
            best_timing = timing_levels[0]
            comparison['analysis']['timing_winner'] = best_timing[0]
            comparison['analysis']['timing_levels_all'] = {name: levels for name, levels in timing_levels}
            
            if len(timing_levels) > 1:
                improvement = timing_levels[1][1] - timing_levels[0][1]
                comparison['analysis']['timing_improvement'] = improvement
            else:
                comparison['analysis']['timing_improvement'] = 0
        else:
            comparison['analysis']['timing_winner'] = 'Unable to compare'
            
        # LUT count comparison
        lut_counts = [(name, result.lut_count) for name, result in flows if result.lut_count is not None]
        if len(lut_counts) >= 2:
            lut_counts.sort(key=lambda x: x[1])  # Sort by LUT count (lower is better)
            best_area = lut_counts[0]
            comparison['analysis']['area_winner'] = best_area[0]
            comparison['analysis']['lut_counts_all'] = {name: count for name, count in lut_counts}
            
            if len(lut_counts) > 1:
                improvement = lut_counts[1][1] - lut_counts[0][1]
                comparison['analysis']['area_improvement'] = improvement
            else:
                comparison['analysis']['area_improvement'] = 0
        else:
            comparison['analysis']['area_winner'] = 'Unable to compare'
            
        # Runtime comparison
        runtimes = [(name, result.runtime) for name, result in flows if result.runtime is not None]
        if len(runtimes) >= 2:
            runtimes.sort(key=lambda x: x[1])  # Sort by runtime (lower is better)
            fastest = runtimes[0]
            comparison['analysis']['runtime_winner'] = fastest[0]
            comparison['analysis']['runtimes_all'] = {name: runtime for name, runtime in runtimes}
            
            if len(runtimes) > 1:
                speedup = runtimes[1][1] / runtimes[0][1]
                comparison['analysis']['speedup'] = speedup
            else:
                comparison['analysis']['speedup'] = 1.0
        
        return comparison
    
    def print_results(self, comparison: Dict[str, Any]):
        """Print comparison results in a nice format."""
        circt = comparison['circt']
        yosys = comparison['yosys']
        hybrid = comparison.get('hybrid')
        analysis = comparison['analysis']
        
        print("\n" + "="*70)
        print("SYNTHESIS COMPARISON RESULTS")
        print("="*70)
        
        # Individual results
        print(f"\n{'CIRCT Results:':<25}")
        print(f"  Success:        {'✓' if circt.success else '✗'}")
        if circt.success:
            print(f"  Timing levels:  {circt.timing_levels or 'N/A'}")
            print(f"  LUT count:      {circt.lut_count or 'N/A'}")
            print(f"  Runtime:        {circt.runtime:.3f}s")
        else:
            print(f"  Error:          {circt.error_message}")
            
        print(f"\n{'Yosys+ABC Results:':<25}")
        print(f"  Success:        {'✓' if yosys.success else '✗'}")
        if yosys.success:
            print(f"  Timing levels:  {yosys.timing_levels or 'N/A'}")
            print(f"  LUT count:      {yosys.lut_count or 'N/A'}")
            print(f"  Runtime:        {yosys.runtime:.3f}s")
        else:
            print(f"  Error:          {yosys.error_message}")
            
        if hybrid:
            print(f"\n{'CIRCT+Yosys Results:':<25}")
            print(f"  Success:        {'✓' if hybrid.success else '✗'}")
            if hybrid.success:
                print(f"  Timing levels:  {hybrid.timing_levels or 'N/A'}")
                print(f"  LUT count:      {hybrid.lut_count or 'N/A'}")
                print(f"  Runtime:        {hybrid.runtime:.3f}s")
            else:
                print(f"  Error:          {hybrid.error_message}")
        
        # Comparison analysis
        successful_flows = [flow for flow in [circt, yosys, hybrid] if flow and flow.success]
        if len(successful_flows) >= 2:
            print(f"\n{'COMPARISON ANALYSIS:':<25}")
            
            # Timing
            timing_winner = analysis.get('timing_winner', 'Unable to compare')
            timing_levels = analysis.get('timing_levels_all', {})
            if timing_winner != 'Unable to compare' and timing_levels:
                improvement = analysis.get('timing_improvement', 0)
                print(f"  Timing:         🏆 {timing_winner}")
                if improvement > 0:
                    print(f"                  ({improvement} levels better than second best)")
                for flow_name, levels in timing_levels.items():
                    marker = "🏆" if flow_name == timing_winner else "  "
                    print(f"                  {marker} {flow_name}: {levels} levels")
            else:
                print(f"  Timing:         {timing_winner}")
                
            # Area
            area_winner = analysis.get('area_winner', 'Unable to compare')
            lut_counts = analysis.get('lut_counts_all', {})
            if area_winner != 'Unable to compare' and lut_counts:
                improvement = analysis.get('area_improvement', 0)
                print(f"  Area:           🏆 {area_winner}")
                if improvement > 0:
                    print(f"                  ({improvement} LUTs fewer than second best)")
                for flow_name, count in lut_counts.items():
                    marker = "🏆" if flow_name == area_winner else "  "
                    print(f"                  {marker} {flow_name}: {count} LUTs")
            else:
                print(f"  Area:           {area_winner}")
                
            # Runtime
            runtime_winner = analysis.get('runtime_winner', 'Unable to compare')
            runtimes = analysis.get('runtimes_all', {})
            speedup = analysis.get('speedup', 1.0)
            if runtime_winner != 'Unable to compare' and runtimes:
                print(f"  Runtime:        🏆 {runtime_winner}")
                if speedup > 1.0:
                    print(f"                  ({speedup:.2f}x faster than second best)")
                for flow_name, runtime in runtimes.items():
                    marker = "🏆" if flow_name == runtime_winner else "  "
                    print(f"                  {marker} {flow_name}: {runtime:.3f}s")
            else:
                print(f"  Runtime:        {runtime_winner}")
        
        print("\n" + "="*70)
    
    def run_comparison(self, input_file: str) -> Dict[str, Any]:
        """Run all synthesis flows and compare results."""
        print(f"Starting synthesis comparison for: {input_file}")
        print(f"LUT-K: {self.lut_k}")
        print(f"Output directory: {self.output_dir}")
        
        # Run CIRCT synthesis
        print(f"\n{'='*50}")
        print("RUNNING CIRCT SYNTHESIS FLOW")
        print("="*50)
        circt_results = self.run_circt_synthesis(input_file)
        
        # Run Yosys synthesis
        print(f"\n{'='*50}")
        print("RUNNING YOSYS+ABC SYNTHESIS FLOW")
        print("="*50)
        yosys_results = self.run_yosys_synthesis(input_file)
        
        # Run Hybrid synthesis
        print(f"\n{'='*50}")
        print("RUNNING CIRCT+YOSYS HYBRID SYNTHESIS FLOW")
        print("="*50)
        hybrid_results = self.run_hybrid_synthesis(input_file)
        
        # Compare results
        comparison = self.compare_results(circt_results, yosys_results, hybrid_results)
        self.print_results(comparison)
        
        # Save comparison report
        report_file = self.output_dir / "comparison_report.json"
        with open(report_file, 'w') as f:
            # Convert SynthesisResults to dict for JSON serialization
            comparison_json = {
                'circt': {
                    'timing_levels': circt_results.timing_levels,
                    'lut_count': circt_results.lut_count,
                    'runtime': circt_results.runtime,
                    'success': circt_results.success,
                    'error_message': circt_results.error_message
                },
                'yosys': {
                    'timing_levels': yosys_results.timing_levels,
                    'lut_count': yosys_results.lut_count,
                    'runtime': yosys_results.runtime,
                    'success': yosys_results.success,
                    'error_message': yosys_results.error_message
                },
                'hybrid': {
                    'timing_levels': hybrid_results.timing_levels,
                    'lut_count': hybrid_results.lut_count,
                    'runtime': hybrid_results.runtime,
                    'success': hybrid_results.success,
                    'error_message': hybrid_results.error_message
                },
                'analysis': comparison['analysis'],
                'config': {
                    'input_file': input_file,
                    'lut_k': self.lut_k,
                    'output_dir': str(self.output_dir)
                }
            }
            json.dump(comparison_json, f, indent=2)
        
        print(f"\nComparison report saved to: {report_file}")
        
        return comparison
    
    def find_verilog_files(self, input_path: str) -> List[str]:
        """Find all .sv and .v files recursively in a directory."""
        verilog_files = []
        path = Path(input_path)
        
        if path.is_file():
            # Single file
            if path.suffix.lower() in ['.sv', '.v']:
                verilog_files.append(str(path))
            else:
                self.log(f"Warning: {path} is not a Verilog file")
        elif path.is_dir():
            # Directory - find all .sv and .v files recursively
            self.log(f"Searching for Verilog files in {path}...")
            for pattern in ['**/*.sv', '**/*.v']:
                files = path.glob(pattern)
                for file_path in files:
                    if file_path.is_file():
                        verilog_files.append(str(file_path))
                        
            verilog_files.sort()  # Sort for consistent ordering
            self.log(f"Found {len(verilog_files)} Verilog files")
        else:
            raise FileNotFoundError(f"Input path does not exist: {input_path}")
            
        return verilog_files
    
    def run_batch_comparison(self, input_path: str) -> Dict[str, Any]:
        """Run comparison on multiple Verilog files."""
        verilog_files = self.find_verilog_files(input_path)
        
        if not verilog_files:
            raise ValueError(f"No Verilog files found in {input_path}")
            
        batch_results = {
            'input_path': input_path,
            'total_files': len(verilog_files),
            'results': {},
            'summary': {
                'successful_comparisons': 0,
                'failed_comparisons': 0,
                'circt_wins_timing': 0,
                'yosys_wins_timing': 0,
                'ties_timing': 0,
                'circt_wins_area': 0,
                'yosys_wins_area': 0,
                'ties_area': 0,
                'total_circt_time': 0.0,
                'total_yosys_time': 0.0,
            }
        }
        
        print(f"Starting batch synthesis comparison for {len(verilog_files)} files")
        print(f"LUT-K: {self.lut_k}")
        print(f"Output directory: {self.output_dir}")
        print("="*80)
        
        for i, verilog_file in enumerate(verilog_files, 1):
            file_name = Path(verilog_file).name
            print(f"\n[{i}/{len(verilog_files)}] Processing: {file_name}")
            print("-" * 60)
            
            try:
                # Create subdirectory for this file's outputs
                file_base = Path(verilog_file).stem
                file_output_dir = self.output_dir / file_base
                
                # Create temporary comparator for this file
                file_comparator = SynthesisComparator(
                    lut_k=self.lut_k,
                    output_dir=str(file_output_dir),
                    verbose=self.verbose
                )
                
                comparison = file_comparator.run_comparison(verilog_file)
                
                # Store results
                batch_results['results'][file_name] = {
                    'file_path': verilog_file,
                    'circt': {
                        'timing_levels': comparison['circt'].timing_levels,
                        'lut_count': comparison['circt'].lut_count,
                        'runtime': comparison['circt'].runtime,
                        'success': comparison['circt'].success,
                        'error_message': comparison['circt'].error_message
                    },
                    'yosys': {
                        'timing_levels': comparison['yosys'].timing_levels,
                        'lut_count': comparison['yosys'].lut_count,
                        'runtime': comparison['yosys'].runtime,
                        'success': comparison['yosys'].success,
                        'error_message': comparison['yosys'].error_message
                    },
                    'analysis': comparison['analysis']
                }
                
                # Update summary statistics
                if comparison['circt'].success and comparison['yosys'].success:
                    batch_results['summary']['successful_comparisons'] += 1
                    
                    # Timing analysis
                    timing_winner = comparison['analysis'].get('timing_winner', 'Unable to compare')
                    if timing_winner == 'CIRCT':
                        batch_results['summary']['circt_wins_timing'] += 1
                    elif timing_winner == 'Yosys+ABC':
                        batch_results['summary']['yosys_wins_timing'] += 1
                    elif timing_winner == 'Tie':
                        batch_results['summary']['ties_timing'] += 1
                        
                    # Area analysis
                    area_winner = comparison['analysis'].get('area_winner', 'Unable to compare')
                    if area_winner == 'CIRCT':
                        batch_results['summary']['circt_wins_area'] += 1
                    elif area_winner == 'Yosys+ABC':
                        batch_results['summary']['yosys_wins_area'] += 1
                    elif area_winner == 'Tie':
                        batch_results['summary']['ties_area'] += 1
                        
                    # Runtime totals
                    if comparison['circt'].runtime:
                        batch_results['summary']['total_circt_time'] += comparison['circt'].runtime
                    if comparison['yosys'].runtime:
                        batch_results['summary']['total_yosys_time'] += comparison['yosys'].runtime
                else:
                    batch_results['summary']['failed_comparisons'] += 1
                    
            except Exception as e:
                print(f"Error processing {file_name}: {e}")
                batch_results['summary']['failed_comparisons'] += 1
                batch_results['results'][file_name] = {
                    'file_path': verilog_file,
                    'error': str(e)
                }
        
        # Print batch summary
        self.print_batch_summary(batch_results)
        
        # Save batch results
        batch_report_file = self.output_dir / "batch_comparison_report.json"
        with open(batch_report_file, 'w') as f:
            json.dump(batch_results, f, indent=2)
        
        print(f"\nBatch comparison report saved to: {batch_report_file}")
        
        return batch_results
    
    def print_batch_summary(self, batch_results: Dict[str, Any]):
        """Print summary of batch comparison results."""
        summary = batch_results['summary']
        
        print("\n" + "="*80)
        print("BATCH SYNTHESIS COMPARISON SUMMARY")
        print("="*80)
        
        print(f"\nFiles Processed:")
        print(f"  Total files:           {batch_results['total_files']}")
        print(f"  Successful comparisons: {summary['successful_comparisons']}")
        print(f"  Failed comparisons:     {summary['failed_comparisons']}")
        
        if summary['successful_comparisons'] > 0:
            print(f"\nTiming Comparison (Logic Levels):")
            print(f"  CIRCT wins:            {summary['circt_wins_timing']}")
            print(f"  Yosys+ABC wins:        {summary['yosys_wins_timing']}")
            print(f"  Ties:                  {summary['ties_timing']}")
            
            print(f"\nArea Comparison (LUT Count):")
            print(f"  CIRCT wins:            {summary['circt_wins_area']}")
            print(f"  Yosys+ABC wins:        {summary['yosys_wins_area']}")
            print(f"  Ties:                  {summary['ties_area']}")
            
            print(f"\nTotal Runtime:")
            print(f"  CIRCT total:           {summary['total_circt_time']:.3f}s")
            print(f"  Yosys+ABC total:       {summary['total_yosys_time']:.3f}s")
            
            if summary['total_circt_time'] > 0 and summary['total_yosys_time'] > 0:
                if summary['total_circt_time'] < summary['total_yosys_time']:
                    speedup = summary['total_yosys_time'] / summary['total_circt_time']
                    print(f"  Overall speedup:       🏆 CIRCT {speedup:.2f}x faster")
                else:
                    speedup = summary['total_circt_time'] / summary['total_yosys_time']
                    print(f"  Overall speedup:       🏆 Yosys+ABC {speedup:.2f}x faster")
        
        print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(
        description="Compare CIRCT and Yosys+ABC synthesis flows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python synth-util.py input.sv
  python synth-util.py --lut-k 4 input.v
  python synth-util.py --output-dir results --verbose input.sv
  python synth-util.py /path/to/verilog/directory
  python synth-util.py --verbose /path/to/benchmarks
        """
    )
    
    parser.add_argument('input_path', help='Input SystemVerilog/Verilog file or directory')
    parser.add_argument('-k', '--lut-k', type=int, default=6, 
                       help='LUT size for both flows (default: 6)')
    parser.add_argument('-o', '--output-dir', default='build',
                       help='Output directory (default: build)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Check if input path exists
    if not os.path.exists(args.input_path):
        print(f"Error: Input path '{args.input_path}' does not exist")
        sys.exit(1)
    
    # Create comparator and run comparison
    comparator = SynthesisComparator(
        lut_k=args.lut_k,
        output_dir=args.output_dir,
        verbose=args.verbose
    )
    
    try:
        # Check if input is a directory or file
        input_path = Path(args.input_path)
        
        if input_path.is_dir():
            # Run batch comparison on directory
            comparison = comparator.run_batch_comparison(args.input_path)
            
            # Exit with error code if any synthesis failed
            if comparison['summary']['failed_comparisons'] > 0:
                print(f"Warning: {comparison['summary']['failed_comparisons']} files failed synthesis")
                sys.exit(1)
        else:
            # Single file comparison
            if input_path.suffix.lower() not in ['.sv', '.v']:
                print(f"Error: Input file '{args.input_path}' must be a SystemVerilog (.sv) or Verilog (.v) file")
                sys.exit(1)
                
            comparison = comparator.run_comparison(args.input_path)
            
            # Exit with error code if all synthesis flows failed
            if not comparison['circt'].success and not comparison['yosys'].success and not comparison['hybrid'].success:
                sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
