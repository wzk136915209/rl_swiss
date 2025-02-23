import yaml
import argparse
import os
from os import path as osp
from time import sleep
from subprocess import Popen
import datetime
import dateutil
from rlkit.launchers import config
from rlkit.launchers.launcher_util import build_nested_variant_generator

if __name__ == '__main__':
    # Arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-e', '--experiment', default='exp_specs/adv_irl.yaml', help='experiment specification file')
    parser.add_argument('--nosrun', help='don\'t use srun', action='store_true')
    args = parser.parse_args()
    with open(args.experiment, 'r') as spec_file:
        spec_string = spec_file.read()
        exp_specs = yaml.load(spec_string)
    
    # generating the variants
    vg_fn = build_nested_variant_generator(exp_specs)
    
    # write all of them to a file
    now = datetime.datetime.now(dateutil.tz.tzlocal())
    timestamp = now.strftime('%Y_%m_%d_%H_%M_%S')
    variants_dir = os.path.join(
        config.LOCAL_LOG_DIR, 'variants-for-'+exp_specs['meta_data']['exp_name'], 'variants-'+timestamp
    )
    os.makedirs(variants_dir)
    with open(os.path.join(variants_dir, 'exp_spec_definition.yaml'), 'w') as f:
        yaml.dump(exp_specs, f, default_flow_style=False)
    num_variants = 0
    for variant in vg_fn():
        i = num_variants
        variant['exp_id'] = i
        with open(os.path.join(variants_dir, '%d.yaml'%i), 'w') as f:
            yaml.dump(variant, f, default_flow_style=False)
            f.flush()
        num_variants += 1
    
    num_workers = min(exp_specs['meta_data']['num_workers'], num_variants)
    exp_specs['meta_data']['num_workers'] = num_workers
    if exp_specs['meta_data']['node_exclusions'] != '':
        exp_specs['meta_data']['node_exclusions'] = '-x ' + exp_specs['meta_data']['node_exclusions']

    # run the processes
    running_processes = []
    args_idx = 0
    if args.nosrun:
        command = 'python {script_path} -e {specs}'
    else:
        command = 'srun --gres=gpu:{num_gpu_per_worker} -c {num_cpu_per_worker} --mem {mem_per_worker} {node_exclusions} -p {partitions} python {script_path} -e {specs}'
    
    command_format_dict = exp_specs['meta_data']

    while (args_idx < num_variants) or (len(running_processes) > 0):
        if (len(running_processes) < num_workers) and (args_idx < num_variants):
            command_format_dict['specs'] = os.path.join(variants_dir, '%i.yaml'%args_idx)
            command_to_run = command.format(**command_format_dict)
            command_to_run = command_to_run.split()
            print(command_to_run)
            p = Popen(command_to_run)
            args_idx += 1
            running_processes.append(p)
        else:
            sleep(1)
        
        new_running_processes = []
        for p in running_processes:
            ret_code = p.poll()
            if ret_code is None:
                new_running_processes.append(p)
        running_processes = new_running_processes
