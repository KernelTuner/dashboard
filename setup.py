from setuptools import setup



setup(
    name="ktdashboard",
    version="0.0.1",
    author="Ben van Werkhoven",
    author_email="b.vanwerkhoven@esciencecenter.nl",
    description=("A dashboard to keep track of Kernel Tuner runs"),
    keywords="auto-tuning gpu computing pycuda cuda pyopencl opencl",
    url="http://benvanwerkhoven.github.io/kernel_tuner/",
    packages=['ktdashboard'],
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development',
        'Topic :: System :: Distributed Computing',
        'Development Status :: 3 - Alpha ',
    ],
    install_requires=['bokeh','pandas','panel'],
    entry_points={'console_scripts': ['ktdashboard = ktdashboard.ktdashboard:cli']},
)
