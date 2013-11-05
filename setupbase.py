# encoding: utf-8
"""
This module defines the things that are used in setup.py for building IPython

This includes:

    * The basic arguments to setup
    * Functions for finding things like packages, package data, etc.
    * A function for checking dependencies.
"""
from __future__ import print_function

#-------------------------------------------------------------------------------
#  Copyright (C) 2008  The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
# Imports
#-------------------------------------------------------------------------------
import errno
import os
import sys

from distutils.command.build_py import build_py
from distutils.command.build_scripts import build_scripts
from distutils.command.install import install
from distutils.command.install_scripts import install_scripts
from distutils.cmd import Command
from glob import glob
from subprocess import call

from setupext import install_data_ext

#-------------------------------------------------------------------------------
# Useful globals and utility functions
#-------------------------------------------------------------------------------

# A few handy globals
isfile = os.path.isfile
pjoin = os.path.join
repo_root = os.path.dirname(os.path.abspath(__file__))

def oscmd(s):
    print(">", s)
    os.system(s)

# Py3 compatibility hacks, without assuming IPython itself is installed with
# the full py3compat machinery.

try:
    execfile
except NameError:
    def execfile(fname, globs, locs=None):
        locs = locs or globs
        exec(compile(open(fname).read(), fname, "exec"), globs, locs)

# A little utility we'll need below, since glob() does NOT allow you to do
# exclusion on multiple endings!
def file_doesnt_endwith(test,endings):
    """Return true if test is a file and its name does NOT end with any
    of the strings listed in endings."""
    if not isfile(test):
        return False
    for e in endings:
        if test.endswith(e):
            return False
    return True

#---------------------------------------------------------------------------
# Basic project information
#---------------------------------------------------------------------------

# release.py contains version, authors, license, url, keywords, etc.
execfile(pjoin(repo_root, 'IPython','core','release.py'), globals())

# Create a dict with the basic information
# This dict is eventually passed to setup after additional keys are added.
setup_args = dict(
      name             = name,
      version          = version,
      description      = description,
      long_description = long_description,
      author           = author,
      author_email     = author_email,
      url              = url,
      download_url     = download_url,
      license          = license,
      platforms        = platforms,
      keywords         = keywords,
      classifiers      = classifiers,
      cmdclass         = {'install_data': install_data_ext},
      )


#---------------------------------------------------------------------------
# Find packages
#---------------------------------------------------------------------------

def find_packages():
    """
    Find all of IPython's packages.
    """
    excludes = ['deathrow', 'quarantine']
    packages = []
    for dir,subdirs,files in os.walk('IPython'):
        package = dir.replace(os.path.sep, '.')
        if any(package.startswith('IPython.'+exc) for exc in excludes):
            # package is to be excluded (e.g. deathrow)
            continue
        if '__init__.py' not in files:
            # not a package
            continue
        packages.append(package)
    return packages

#---------------------------------------------------------------------------
# Find package data
#---------------------------------------------------------------------------

def find_package_data():
    """
    Find IPython's package_data.
    """
    # This is not enough for these things to appear in an sdist.
    # We need to muck with the MANIFEST to get this to work
    
    # exclude static things that we don't ship (e.g. mathjax)
    excludes = ['mathjax']
    
    # add 'static/' prefix to exclusions, and tuplify for use in startswith
    excludes = tuple([os.path.join('static', ex) for ex in excludes])
    
    # walk notebook resources:
    cwd = os.getcwd()
    os.chdir(os.path.join('IPython', 'html'))
    static_walk = list(os.walk('static'))
    static_data = []
    for parent, dirs, files in static_walk:
        if parent.startswith(excludes):
            continue
        for f in files:
            static_data.append(os.path.join(parent, f))

    os.chdir(os.path.join('tests',))
    js_tests = glob('casperjs/*.*') +  glob('casperjs/*/*')
    os.chdir(cwd)

    package_data = {
        'IPython.config.profile' : ['README*', '*/*.py'],
        'IPython.core.tests' : ['*.png', '*.jpg'],
        'IPython.testing' : ['*.txt'],
        'IPython.testing.plugin' : ['*.txt'],
        'IPython.html' : ['templates/*'] + static_data,
        'IPython.html.tests' : js_tests,
        'IPython.qt.console' : ['resources/icon/*.svg'],
        'IPython.nbconvert' : ['templates/*.tpl', 'templates/latex/*.tplx',
            'templates/latex/skeleton/*.tplx', 'templates/skeleton/*', 
            'templates/reveal_internals/*.tpl', 'tests/files/*.*',
            'exporters/tests/files/*.*'],
        'IPython.nbformat' : ['tests/*.ipynb']
    }
    return package_data


#---------------------------------------------------------------------------
# Find data files
#---------------------------------------------------------------------------

def make_dir_struct(tag,base,out_base):
    """Make the directory structure of all files below a starting dir.

    This is just a convenience routine to help build a nested directory
    hierarchy because distutils is too stupid to do this by itself.

    XXX - this needs a proper docstring!
    """

    # we'll use these a lot below
    lbase = len(base)
    pathsep = os.path.sep
    lpathsep = len(pathsep)

    out = []
    for (dirpath,dirnames,filenames) in os.walk(base):
        # we need to strip out the dirpath from the base to map it to the
        # output (installation) path.  This requires possibly stripping the
        # path separator, because otherwise pjoin will not work correctly
        # (pjoin('foo/','/bar') returns '/bar').

        dp_eff = dirpath[lbase:]
        if dp_eff.startswith(pathsep):
            dp_eff = dp_eff[lpathsep:]
        # The output path must be anchored at the out_base marker
        out_path = pjoin(out_base,dp_eff)
        # Now we can generate the final filenames. Since os.walk only produces
        # filenames, we must join back with the dirpath to get full valid file
        # paths:
        pfiles = [pjoin(dirpath,f) for f in filenames]
        # Finally, generate the entry we need, which is a pari of (output
        # path, files) for use as a data_files parameter in install_data.
        out.append((out_path, pfiles))

    return out


def find_data_files():
    """
    Find IPython's data_files.

    Most of these are docs.
    """

    docdirbase  = pjoin('share', 'doc', 'ipython')
    manpagebase = pjoin('share', 'man', 'man1')

    # Simple file lists can be made by hand
    manpages = [f for f in glob(pjoin('docs','man','*.1.gz')) if isfile(f)]
    if not manpages:
        # When running from a source tree, the manpages aren't gzipped
        manpages = [f for f in glob(pjoin('docs','man','*.1')) if isfile(f)]

    igridhelpfiles = [f for f in glob(pjoin('IPython','extensions','igrid_help.*')) if isfile(f)]

    # For nested structures, use the utility above
    example_files = make_dir_struct(
        'data',
        pjoin('docs','examples'),
        pjoin(docdirbase,'examples')
    )
    manual_files = make_dir_struct(
        'data',
        pjoin('docs','html'),
        pjoin(docdirbase,'manual')
    )

    # And assemble the entire output list
    data_files = [ (manpagebase, manpages),
                   (pjoin(docdirbase, 'extensions'), igridhelpfiles),
                   ] + manual_files + example_files

    return data_files


def make_man_update_target(manpage):
    """Return a target_update-compliant tuple for the given manpage.

    Parameters
    ----------
    manpage : string
      Name of the manpage, must include the section number (trailing number).

    Example
    -------

    >>> make_man_update_target('ipython.1') #doctest: +NORMALIZE_WHITESPACE
    ('docs/man/ipython.1.gz',
     ['docs/man/ipython.1'],
     'cd docs/man && gzip -9c ipython.1 > ipython.1.gz')
    """
    man_dir = pjoin('docs', 'man')
    manpage_gz = manpage + '.gz'
    manpath = pjoin(man_dir, manpage)
    manpath_gz = pjoin(man_dir, manpage_gz)
    gz_cmd = ( "cd %(man_dir)s && gzip -9c %(manpage)s > %(manpage_gz)s" %
               locals() )
    return (manpath_gz, [manpath], gz_cmd)

# The two functions below are copied from IPython.utils.path, so we don't need
# to import IPython during setup, which fails on Python 3.

def target_outdated(target,deps):
    """Determine whether a target is out of date.

    target_outdated(target,deps) -> 1/0

    deps: list of filenames which MUST exist.
    target: single filename which may or may not exist.

    If target doesn't exist or is older than any file listed in deps, return
    true, otherwise return false.
    """
    try:
        target_time = os.path.getmtime(target)
    except os.error:
        return 1
    for dep in deps:
        dep_time = os.path.getmtime(dep)
        if dep_time > target_time:
            #print "For target",target,"Dep failed:",dep # dbg
            #print "times (dep,tar):",dep_time,target_time # dbg
            return 1
    return 0


def target_update(target,deps,cmd):
    """Update a target with a given command given a list of dependencies.

    target_update(target,deps,cmd) -> runs cmd if target is outdated.

    This is just a wrapper around target_outdated() which calls the given
    command if target is outdated."""

    if target_outdated(target,deps):
        os.system(cmd)

#---------------------------------------------------------------------------
# Find scripts
#---------------------------------------------------------------------------

def find_entry_points():
    """Find IPython's scripts.

    if entry_points is True:
        return setuptools entry_point-style definitions
    else:
        return file paths of plain scripts [default]

    suffix is appended to script names if entry_points is True, so that the
    Python 3 scripts get named "ipython3" etc.
    """
    ep = [
            'ipython%s = IPython:start_ipython',
            'ipcontroller%s = IPython.parallel.apps.ipcontrollerapp:launch_new_instance',
            'ipengine%s = IPython.parallel.apps.ipengineapp:launch_new_instance',
            'iplogger%s = IPython.parallel.apps.iploggerapp:launch_new_instance',
            'ipcluster%s = IPython.parallel.apps.ipclusterapp:launch_new_instance',
            'iptest%s = IPython.testing.iptestcontroller:main',
            'irunner%s = IPython.lib.irunner:main',
        ]
    suffix = str(sys.version_info[0])
    return [e % '' for e in ep] + [e % suffix for e in ep]

script_src = """#!{executable}
# This script was automatically generated by setup.py
from {mod} import {func}
{func}()
"""

class build_scripts_entrypt(build_scripts):
    def run(self):
        self.mkpath(self.build_dir)
        outfiles = []
        for script in find_entry_points():
            name, entrypt = script.split('=')
            name = name.strip()
            entrypt = entrypt.strip()
            outfile = os.path.join(self.build_dir, name)
            outfiles.append(outfile)
            print('Writing script to', outfile)

            mod, func = entrypt.split(':')
            with open(outfile, 'w') as f:
                f.write(script_src.format(executable=sys.executable,
                                          mod=mod, func=func))

        return outfiles, outfiles

class install_lib_symlink(Command):
    user_options = [
        ('install-dir=', 'd', "directory to install to"),
        ]

    def initialize_options(self):
        self.install_dir = None

    def finalize_options(self):
        self.set_undefined_options('symlink',
                                   ('install_lib', 'install_dir'),
                                  )

    def run(self):
        if sys.platform == 'win32':
            raise Exception("This doesn't work on Windows.")
        pkg = os.path.join(os.getcwd(), 'IPython')
        dest = os.path.join(self.install_dir, 'IPython')
        print('symlinking %s -> %s' % (pkg, dest))
        try:
            os.symlink(pkg, dest)
        except OSError as e:
            if e.errno == errno.EEXIST:
                print('ALREADY EXISTS')
            else:
                raise

class install_symlinked(install):
    def run(self):
        if sys.platform == 'win32':
            raise Exception("This doesn't work on Windows.")
        install.run(self)
    
    # 'sub_commands': a list of commands this command might have to run to
    # get its work done.  See cmd.py for more info.
    sub_commands = [('install_lib_symlink', lambda self:True),
                    ('install_scripts_sym', lambda self:True),
                   ]

class install_scripts_for_symlink(install_scripts):
    """Redefined to get options from 'symlink' instead of 'install'.
    
    I love distutils almost as much as I love setuptools.
    """
    def finalize_options(self):
        self.set_undefined_options('build', ('build_scripts', 'build_dir'))
        self.set_undefined_options('symlink',
                                   ('install_scripts', 'install_dir'),
                                   ('force', 'force'),
                                   ('skip_build', 'skip_build'),
                                  )

#---------------------------------------------------------------------------
# Verify all dependencies
#---------------------------------------------------------------------------

def check_for_dependencies():
    """Check for IPython's dependencies.

    This function should NOT be called if running under setuptools!
    """
    from setupext.setupext import (
        print_line, print_raw, print_status,
        check_for_sphinx, check_for_pygments,
        check_for_nose, check_for_pexpect,
        check_for_pyzmq, check_for_readline,
        check_for_jinja2, check_for_tornado
    )
    print_line()
    print_raw("BUILDING IPYTHON")
    print_status('python', sys.version)
    print_status('platform', sys.platform)
    if sys.platform == 'win32':
        print_status('Windows version', sys.getwindowsversion())

    print_raw("")
    print_raw("OPTIONAL DEPENDENCIES")

    check_for_sphinx()
    check_for_pygments()
    check_for_nose()
    check_for_pexpect()
    check_for_pyzmq()
    check_for_tornado()
    check_for_readline()
    check_for_jinja2()

#---------------------------------------------------------------------------
# VCS related
#---------------------------------------------------------------------------

# utils.submodule has checks for submodule status
execfile(pjoin('IPython','utils','submodule.py'), globals())

class UpdateSubmodules(Command):
    """Update git submodules
    
    IPython's external javascript dependencies live in a separate repo.
    """
    description = "Update git submodules"
    user_options = []
    
    def initialize_options(self):
        pass
    
    def finalize_options(self):
        pass
    
    def run(self):
        failure = False
        try:
            self.spawn('git submodule init'.split())
            self.spawn('git submodule update --recursive'.split())
        except Exception as e:
            failure = e
            print(e)
        
        if not check_submodule_status(repo_root) == 'clean':
            print("submodules could not be checked out")
            sys.exit(1)


def git_prebuild(pkg_dir, build_cmd=build_py):
    """Return extended build or sdist command class for recording commit
    
    records git commit in IPython.utils._sysinfo.commit
    
    for use in IPython.utils.sysinfo.sys_info() calls after installation.
    
    Also ensures that submodules exist prior to running
    """
    
    class MyBuildPy(build_cmd):
        ''' Subclass to write commit data into installation tree '''
        def run(self):
            build_cmd.run(self)
            # this one will only fire for build commands
            if hasattr(self, 'build_lib'):
                self._record_commit(self.build_lib)
        
        def make_release_tree(self, base_dir, files):
            # this one will fire for sdist
            build_cmd.make_release_tree(self, base_dir, files)
            self._record_commit(base_dir)
        
        def _record_commit(self, base_dir):
            import subprocess
            proc = subprocess.Popen('git rev-parse --short HEAD',
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    shell=True)
            repo_commit, _ = proc.communicate()
            repo_commit = repo_commit.strip().decode("ascii")
            
            out_pth = pjoin(base_dir, pkg_dir, 'utils', '_sysinfo.py')
            if os.path.isfile(out_pth) and not repo_commit:
                # nothing to write, don't clobber
                return
            
            print("writing git commit '%s' to %s" % (repo_commit, out_pth))
            
            # remove to avoid overwriting original via hard link
            try:
                os.remove(out_pth)
            except (IOError, OSError):
                pass
            with open(out_pth, 'w') as out_file:
                out_file.writelines([
                    '# GENERATED BY setup.py\n',
                    'commit = "%s"\n' % repo_commit,
                ])
    return require_submodules(MyBuildPy)


def require_submodules(command):
    """decorator for instructing a command to check for submodules before running"""
    class DecoratedCommand(command):
        def run(self):
            if not check_submodule_status(repo_root) == 'clean':
                print("submodules missing! Run `setup.py submodule` and try again")
                sys.exit(1)
            command.run(self)
    return DecoratedCommand

#---------------------------------------------------------------------------
# Notebook related
#---------------------------------------------------------------------------

class CompileCSS(Command):
    """Recompile Notebook CSS
    
    Regenerate the compiled CSS from LESS sources.
    
    Requires various dev dependencies, such as fabric and lessc.
    """
    description = "Recompile Notebook CSS"
    user_options = []
    
    def initialize_options(self):
        pass
    
    def finalize_options(self):
        pass
    
    def run(self):
        call("fab css", shell=True, cwd=pjoin(repo_root, "IPython", "html"))
