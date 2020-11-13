""" Phonetic task zerospeech 2021 """
import collections
from dataclasses import dataclass
from pathlib import Path
from itertools import chain
from typing import Optional
from enum import Enum

import numpy as np
import yaml
import joblib

from zerospeech2021 import exception
from zerospeech2021.phonetic_eval import eval_ABX

LIBRISPEECH_SETS = {
    'dev': ['dev-clean', 'dev-other'],
    'test': ['test-clean', 'test-other']}


ABXFileTypes = Enum('ABXFileTypes',
                    '.pt .npy .txt .wav .flac .mp3')
ABXMode = Enum('ABXMode', 'all within across')

ABXDistanceMode = Enum('ABXDistanceMode',
                       'euclidian cosine kl kl_symmetric')


@dataclass
class AbxArguments:
    """ List of arguments to provide to abx in phonetic_eval.abx"""
    # path to input data
    path_data: str
    # path to item file
    path_item_file: str
    # Path to a CPC checkpoint
    path_checkpoint: Optional[str] = None
    # size of a single feature
    feature_size: Optional[float] = float(0.1)
    # Use the GPU to compute distances
    cuda: bool = True
    # extension (of input files ?)
    file_extension: ABXFileTypes = '.txt'
    # Choose the mode of the ABX score to compute
    mode: ABXMode = 'all'
    # Choose the kind of distance to use to compute
    distance_mode: ABXDistanceMode = 'cosine'
    # Max size of a group while computing the ABX score
    max_size_group: int = 10
    # When computing the ABX across score, maximum
    # number of speaker X to sample per couple A,B.
    max_x_across: int = 5
    # location to output the results
    out: Optional[str] = None


def load_meta_args(features_location: Path):
    with (features_location / 'meta.yaml').open() as fp:
        meta = yaml.safe_load(fp)
    try:
        metric = meta['parameters']['phonetic']['metric']
    except KeyError:
        raise ValueError("The metric must be specified in the meta.yaml phonetic section")

    try:
        features_size = float(meta['parameters']['phonetic']['features_size'])

        return dict(features_size=features_size, metric=metric)
    except KeyError:
        raise ValueError("feature size must be defined in the meta.yaml")


def get_input_files(dataset_directory, _set, file_type):
    """ Returns a list of all the files in a set """
    res = []
    for s in LIBRISPEECH_SETS[_set]:
        res.append((dataset_directory / s).rglob(f"*.{file_type}"))
    return list(chain(*res))


def get_submitted_files(submission_directory, _set):
    """ Returns a list of all the files in a set """
    res = []
    for s in LIBRISPEECH_SETS[_set]:
        res.append((submission_directory / s).rglob("*"))
    return list(chain(*res))


def _validate_file(source_file, submission, dataset):
    """Ensure a file has the correct format

    Verifies that a feature file is a 2D numpy array of floats and it matches a
    file in the dataset.

    :param source_file: input file from dataset
    :param submission: location of submitted files
    :param dataset: location of dataset

    :return: a pair (target_file, ncols), where target_file is the file in the
      submission directory and ncols is the number of columns in the array.

    :raises exception.EntryMissingError if an entry is not present

    """
    try:
        target_file = submission / source_file.relative_to(dataset)
        target_file = target_file.with_suffix('.txt')
        if not target_file.is_file():
            raise exception.EntryMissingError(
                source=source_file, expected=target_file)

        try:
            array = np.loadtxt(str(target_file))
        except Exception:
            raise exception.FileFormatError(
                target_file, 'not a valid numpy array')

        if array.dtype != np.dtype('float'):
            raise exception.FileFormatError(
                target_file, "array loaded is not dtype = float")

        if array.ndim != 2:
            raise exception.FileFormatError(
                target_file, 'not a 2D array')
    except exception.ValidationError as error:
        return str(error), None, None

    return None, target_file, array.shape[1]


def validate(submission, dataset, kind, njobs=1):
    """Validate a subset of the submissions for the phonetic task

    :param submission_directory: location of submissions
    :param dataset_directory: location of data
    :param kind: subset type (dev | test)
    :param njobs: number of paralle processes to use for validation

    :raise ValidationError: if the submission is not valid

    """
    if kind not in LIBRISPEECH_SETS.keys():
        raise ValueError(f'kind must be "dev" or "test", it is {kind}')

    input_files = get_input_files(dataset, kind, "wav")
    if not input_files:
        raise exception.ValidationError(
            f'found no wav files in {dataset}')

    submitted_files = get_submitted_files(submission, kind)
    if not submitted_files:
        raise exception.ValidationError(
            f'found no files in {submission}')

    # ensure we have only .txt files in submission
    no_txt_files = [str(f) for f in submitted_files if f.suffix != '.txt']
    if no_txt_files:
        raise exception.MismatchError('extra files found', [], no_txt_files)

    # ensure that there are no duplicates
    duplicates = [
        f for f, n in collections.Counter(submitted_files).items() if n > 1
    ]
    if duplicates:
        raise exception.MismatchError('duplicates found', [], duplicates)

    # check that necessary files are present and valid
    valid_entries = joblib.Parallel(n_jobs=njobs)(
        joblib.delayed(_validate_file)(f, submission, dataset)
        for f in input_files)
    errors, valid_entries, ncols = zip(*valid_entries)

    # ensure there are no detected errors
    errors = [e for e in errors if e]
    if errors:
        for e in errors[:10]:
            print(f'ERROR: {e}')
        if len(errors) > 10:
            print('ERROR: ... and {len(errors - 10)} more!')
        raise exception.ValidationError(f'error detected in phonetic {kind}')

    # ensure all submitted files have the same number of columns
    if len(set(ncols)) != 1:
        raise exception.ValidationError(
            f'all files must have the same number of columns '
            f'but have: {set(ncols)}')

    if collections.Counter(submitted_files) != collections.Counter(valid_entries):
        raise exception.MismatchError(
            'mismatch in filenames', valid_entries, submitted_files)


def evaluate(features_location: Path, dataset: Path, output_dir: Path, kind):
    meta_values = load_meta_args(features_location.parents[0])
    metric = meta_values.get("metric", 'cosine')
    frame_shift = meta_values.get("feature_size", 0.01)

    for _set in LIBRISPEECH_SETS[kind]:
        arg_obj = AbxArguments(
            path_data=str(features_location / _set),
            path_item_file=f'{(dataset / _set / f"{_set}.item")}',
            distance_mode=f"{metric}", feature_size=frame_shift,
            out=f"{output_dir}")
        eval_ABX.main(arg_obj=arg_obj)
