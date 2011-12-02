from setuptools import setup, find_packages
import os

version = '0.1a1dev'

install_requires = [
    'setuptools',
    'python-daemon',
    'pyinotify',
    ]

tests_require = [
    'pytest',
    'pycurl',
    ]

setup(name='document_chain',
      version=version,
      description="A simple document chain processing",
      long_description=open("README.rst").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='Document processing',
      author='Tarentis',
      author_email='contact@tarentis.fr',
      url='http://tarentis.fr',
      license='GPL',
      packages=find_packages('src', exclude=['ez_setup']),
      package_dir={'': 'src'},
      include_package_data=True,
      zip_safe=False,
      tests_require=tests_require,
      install_requires=install_requires,
      extras_require={'test': tests_require},
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      runner = document_chain.runner:main
      """,
      )
