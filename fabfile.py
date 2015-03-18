import os
from os.path import normpath, dirname, basename

from fabric.api import *
from fabric.contrib.project import rsync_project
from fabric.contrib import console
from fabric import utils
from fabric.colors import red, green


PROJECT_FOLDER = basename(normpath(dirname(__file__)))
PRODUCTION_SERVER = '127.0.0.1'
STAGING_SERVER = '127.0.0.1'

VALID_HOSTS = ('staging',
               'production', )

env.home = '/srv/'
env.project = PROJECT_FOLDER

SSH_USERNAME = None
if not SSH_USERNAME:
    import getpass
    SSH_USERNAME = getpass.getuser()


env.RSYNC_EXCLUDE = [
    '.DS_Store',
    '.hg',
    '*.pyc',
    '*.py.ex',
    '*.example',
]


def _setup_path():
    # /srv/staging
    env.root = os.path.join(env.home, env.environment)
    # local directory where this file is
    env.local_path = os.path.dirname(__file__)
    # project directory
    env.project_root = os.path.join(env.root, env.project)


def install_requirements(host_string):
    """Install docker & fig to host"""
    with settings(host_string=host_string):
        # ============= DOCKER =============
        # Add key
        sudo('apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 '
             '--recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9')
        sudo('sh -c "echo deb https://get.docker.io/ubuntu docker main  '
             '> /etc/apt/sources.list.d/docker.list"')
        # Update
        print(green('Updating...'))
        with hide('output'):
            sudo('apt-get update')
        # Install docker
        print(green('Installing Docker...'))
        with hide('output'):
            sudo('apt-get install -y lxc-docker')

        # ============= FIG =============
        # Make sure curl is installed
        sudo('apt-get install -y curl')
        # Install fig
        sudo('curl -L https://github.com/docker/fig/releases/download/1.0.1'
             '/fig-`uname -s`-`uname -m` > /usr/local/bin/fig; chmod +x '
             '/usr/local/bin/fig')


def sync(host_string):
    """Sync project to host"""
    # sync opts for rsync
    extra_opts = '--omit-dir-times --chmod=u+rw -L --chmod=o-rw'

    # Run commands on host...
    with settings(host_string=host_string):
        # dir
        sudo('mkdir -p %(root)s' % env)
        sudo('mkdir -p %(project_root)s' % env)
        sudo('chown -R %(user)s:%(user)s %(project_root)s' % env)

        # sync
        print(red("rsync starting"))
        rsync_project(
            local_dir=env.local_path,
            remote_dir=env.root,
            exclude=env.RSYNC_EXCLUDE,
            delete=True,
            extra_opts=extra_opts,
        )


def build_container(host_string):
    # Run commands on host...
    with settings(host_string=host_string):
        # cd to project
        with cd(env.project_root):
            print(green('Start building container on %s:%s' %
                        (host_string, env.project_root)))
            with settings(warn_only=True):
                build = sudo('fig build')
            if build.failed:
                print(red('Build failed on %s:%s' %
                          (host_string, env.project_root)))
                utils.abort('Failed to build on %s' % env.environment)
            print(green('Build successful'))


def stop_container(host_string):
    # Run commands on host...
    with settings(host_string=host_string):
        # cd to project
        with cd(env.project_root):
            # Ask nicely for container to stop
            with settings(warn_only=True):
                stop = sudo('fig stop')
            # It's not listening! We have to kill it!
            if stop.failed:
                sudo('fig kill')

            print(green('Containers stopped'))


def start_container(host_string):
    # Run commands on host...
    with settings(host_string=host_string):
        # cd to project
        with cd(env.project_root):
            with settings(warn_only=True):
                start = sudo('fig up -d')
            if start.failed:
                print(red('Containers failed to start on %s:%s' %
                          (host_string, env.project_root)))
                utils.abort('Start failed on %s' % env.environment)
            print(green('Containers are running on %s' % env.environment))


@task
def show_version_info(host):
    """Show docker & fig versions installed on :host"""
    if host == 'production':
        host_string = PRODUCTION_SERVER
    else:
        host_string = STAGING_SERVER

    with settings(host_string=host_string):
        with hide('output'):
            d = sudo('docker version')
            f = sudo('fig --version')
        print('==============  DOCKER  ===============')
        print(green('%s' % d))
        print('==============    FIG    ==============')
        print(green('%s' % f))
        print('=======================================')


@task
def create_new_harbour(host):
    """Create a new harbour to :host"""
    if host not in VALID_HOSTS:
        utils.abort('Please enter a valid host')
    env.user = SSH_USERNAME
    env.environment = host
    if host == 'production':
        host_string = PRODUCTION_SERVER
    else:
        host_string = STAGING_SERVER

    _setup_path()
    require('root')
    print(green('Creating a new harbour to %s (%s)' % (host, host_string)))
    if not console.confirm('Continue?',
                           default=False):
                utils.abort('Deployment aborted.')
    # install docker and fig to host machine
    install_requirements(host_string)
    # sync
    sync(host_string)
    # build container
    build_container(host_string)
    # start container
    start_container(host_string)
    # show some info...
    show_version_info(host)


@task
def container_status(host):
    """Displays container status on :host"""
    if host not in VALID_HOSTS:
        utils.abort('Please enter a valid host')

    env.user = SSH_USERNAME
    env.environment = host
    if host == 'production':
        host_string = PRODUCTION_SERVER
    else:
        host_string = STAGING_SERVER
    _setup_path()

    require('root')
    with settings(host_string=host_string):
        with cd(env.project_root):
            print(green('Info about containers in %s:%s'
                        % (host_string, env.project_root)))
            with settings(warn_only=True):
                r = run('fig ps')
            if r.failed:
                print(red('No containers found on %s:%s'
                          % (host_string, env.project_root)))


@task
def container_stop(host):
    """Stop container on :host"""
    if host not in VALID_HOSTS:
        utils.abort('Please enter a valid host')

    env.user = SSH_USERNAME
    env.environment = host
    if host == 'production':
        host_string = PRODUCTION_SERVER
    else:
        host_string = STAGING_SERVER
    _setup_path()

    require('root')
    stop_container(host_string)


@task
def container_restart(host):
    """Restart container on :host"""
    if host not in VALID_HOSTS:
        utils.abort('Please enter a valid host')

    env.user = SSH_USERNAME
    env.environment = host
    if host == 'production':
        host_string = PRODUCTION_SERVER
    else:
        host_string = STAGING_SERVER
    _setup_path()

    require('root')
    stop_container(host_string)
    start_container(host_string)