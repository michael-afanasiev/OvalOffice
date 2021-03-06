import io
import os

import click

from oval_office_2 import utilities
from oval_office_2.job_queue import JobQueue
from . import task


class MakeVTK(task.Task):
    """Submits a MakeVTK job on the remote cluster.

    """

    def __init__(self, remote_machine, config, sbatch_dict, nslices, vtk_type):
        super(MakeVTK, self).__init__(remote_machine, config)
        self.sbatch_dict = sbatch_dict
        self.files = None
        self.nslices = nslices
        self.vtk_type = vtk_type

    def check_pre_staging(self):
        pass

    def stage_data(self):
        if self.vtk_type == 'smoothed_kernel':
            self.files = ['bulk_betah_kernel_smooth', 'bulk_betav_kernel_smooth',
                          'bulk_c_kernel_smooth', 'eta_kernel_smooth', 'hess_inv_kernel_smooth']
            file_src_dir = os.path.join(self.config.optimization_dir, 'PROCESSED_KERNELS')

        elif self.vtk_type == 'raw_kernel':
            self.files = ['bulk_betah_kernel', 'bulk_betav_kernel', 'bulk_c_kernel',
                          'eta_kernel', 'hess_inv_kernel']
            file_src_dir = os.path.join(self.config.optimization_dir, 'PROCESSED_KERNELS')

        elif self.vtk_type == 'model':
            self.files = ['vsh', 'vsv']
            file_src_dir = os.path.join(self.config.solver_dir, 'MESH', 'DATABASES_MPI')

        kernel_output_dir = os.path.join(self.config.optimization_dir, 'VTK_FILES') # WHY THIS?
        topo_dir = os.path.join(self.config.solver_dir, 'MESH', 'DATABASES_MPI')
        self.remote_machine.makedir(kernel_output_dir)

        # Write slices.txt
        slices = ""
        slices_path = os.path.join(self.config.optimization_dir, 'VTK_FILES', 'slices.txt')
        for i in range(self.nslices):
            slices += str(i) + "\n"
        with self.remote_machine.ftp_connection.file(slices_path, 'wt') as fh:
            fh.write(slices)

        # Need to write a specific sbatch script for each file.
        for element in self.files:
            self.sbatch_dict['execute'] = 'srun ./bin/xcombine_vol_data_vtk ./VTK_FILES/slices.txt {} {} {} {} 0 1\n'\
                                            .format(element, topo_dir, file_src_dir, kernel_output_dir)
            self.sbatch_dict['job_name'] = 'make_vtk_{}'.format(element)
            self.sbatch_dict['error'] = 'make_vtk_{}.stderr'.format(element)
            self.sbatch_dict['output'] = 'make_vtk_{}.stdout'.format(element)

            # Write sbatch.
            with io.open(utilities.get_template_file('sbatch'), 'r') as fh:
                sbatch_string = fh.read().format(**self.sbatch_dict)
                sbatch_path = os.path.join(self.config.optimization_dir, 'run_make_vtk_{}.sbatch'.format(element))
            with self.remote_machine.ftp_connection.file(sbatch_path, 'wt') as fh:
                fh.write(sbatch_string)

    def check_post_staging(self):
        pass

    def run(self):
        queue = JobQueue(self.remote_machine, name="Make VTK")
        for element in self.files:
                exec_command = "sbatch run_make_vtk_{}.sbatch".format(element)
                _, so, _ = self.remote_machine.execute_command(exec_command,
                                                               workdir=self.config.optimization_dir)
                queue.add_job(utilities.get_job_number_from_stdout(so))
        queue.flash_report(10)

    def check_post_run(self):
        pass
