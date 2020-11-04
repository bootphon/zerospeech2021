#!/usr/bin/env python
"""Setup script for the zerospeech2021 Python package"""

import codecs
import setuptools

import numpy
from Cython.Build import cythonize

import zerospeech2021


setuptools.setup(
    # general description
    name='zerospeech2021',
    description="Evaluation and validation tools for ZeroSpeech2021",
    version=zerospeech2021.__version__,

    # python package dependencies
    install_requires=codecs.open(
        'requirements.txt', encoding='utf-8').readlines(),
    setup_requires=['Cython', 'numpy'],

    # include Python code
    packages=setuptools.find_packages(),
    ext_modules=cythonize(
        setuptools.Extension(
            "libri_light_dtw",
            ["zerospeech2021/libri_light_eval/ABX_src/dtw.pyx"],
            include_dirs=[numpy.get_include()])),
    zip_safe=True,

    # the command-line scripts to export
    entry_points={
        'console_scripts': [
            'zerospeech2021-validate = zerospeech2021.validate_cmd:validate',
            'zerospeech2021-evaluate = zerospeech2021.evaluate_cmd:evaluate'
            # 'libri-abx = zerospeech2021.libri_light_eval.eval_ABX:run_as_cmd'
        ]
    },

    # metadata
    author='CoML team',
    author_email='zerospeech2021@gmail.com',
    license='GPL3',
    url='https://zerospeech.com/2021',
    long_description=codecs.open('README.md', encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    python_requires='>=3.7',
)
