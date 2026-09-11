#!/bin/bash --login
#SBATCH --job-name=tt-e3a
#SBATCH --partition=multicore_small
#SBATCH --constraint=skylake
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --array=0-11%4
#SBATCH --output=slurm-e3a-%A_%a.out
#SBATCH --error=slurm-e3a-%A_%a.err

set -euo pipefail
umask 077
: "${E3A_MANIFEST_SHA256:?Supply the independently recorded manifest SHA-256}"
cd "${SLURM_SUBMIT_DIR:?Submit from the sealed bundle root}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=false PYTHONDONTWRITEBYTECODE=1
exec srun --cpu-bind=cores /scratch/h99877sm/traffictwin/envs/jax0430-py311/bin/python -u \
    campaign.py execute-cell "${SLURM_ARRAY_TASK_ID}" --manifest-sha256 "${E3A_MANIFEST_SHA256}"
