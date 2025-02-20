#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2018 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import re

from ansible.module_utils.basic import AnsibleModule

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = """
---
module: Podman Image
author:
    - Sam Doran (@samdoran)
version_added: '2.8'
short_description: Pull images for use by podman
notes: []
description:
    - Build, pull, or push images using Podman.
options:
  name:
    description:
      - Name of the image to pull, push, or delete. It may contain a tag using
        the format C(image:tag).
    required: True
  tag:
    description:
      - Tag of the image to pull, push, or delete.
    default: "latest"
  pull:
    description: Whether or not to pull the image.
    default: True
  push:
    description: Whether or not to push an image.
    default: False
  path:
    description: Path to directory containing the build file.
  force:
    description:
      - Whether or not to force push or pull an image. When building, force
        the build even if the image already exists.
  state:
    description:
      - Whether an image should be present, absent, or built.
    default: "present"
    choices:
      - present
      - absent
      - build
  tls_verify:
    description:
      - Require HTTPS and validate certificates when pulling or pushing. Also
        used during build if a pull or push is necessary.
    default: True
    aliases:
      - tlsverify
  auth_file:
    description:
      - Path to file containing authorization credentials to the remote
        registry
    aliases:
      - authfile
  build_args:
    description: Arguments that control image build.
    suboptions:
      annotation:
        description:
          - Dictionory of key=value pairs to add to the image. Only
            works with OCI images. Ignored for Docker containers.
        type: "str"
      force_rm:
        description:
          - Always remove intermediate containers after a build, even if
            the build is unsuccessful.
        type: bool
        default: False
      format:
        descritption:
          - Format of the built image.
        choices:
          - docker
          - ock
        deafault: "oci"
      cache:
        description:
          - Whether or not to use cached layers when building an image
        type: bool
        default: True
      rm:
        description: Remove intermediate containers after a successful build
        type: bool
        default: True
  push_args:
    description: Arguments that control pushing images.
    suboptions:
      compress:
        description:
          - Compress tarball image layers when pushing to a directory using the
            'dir' transport.
        type: bool
      format:
        description:
          - Manifest type to use when pushing an image using the
            'dir' transport (default is manifest type of source)
        choices:
          - oci
          - v2s1
          - v2s2
      remove_signatures:
        description: Discard any pre-existing signatures in the image
        type: bool
      sign_by:
        description:
          - Path to a key file to use to sign the image.
      dest:
        description: Path or URL where image will be pushed.
      transport:
        description:
          - Transport to use when pushing in image. If no transport is set,
            will attempt to push to a remote registry.
        choices:
          - dir
          - docker-archive
          - docker-daemon
          - oci-archive
          - ostree

"""

EXAMPLES = """
- name: Pull an image
  podman_image:
    name: quay.io/bitnami/wildfly

- name: Remove an image
  podman_image:
    name: quay.io/bitnami/wildfly
    state: absent

- name: Pull a specific version of an image
  podman_image:
    name: redis
    tag: 4

- name: Build a basic OCI image
  podman_image:
    name: nginx
    path: /path/to/build/dir

- name: Build a basic OCI image with advanced parameters
  podman_image:
    name: nginx
    path: /path/to/build/dir
    build_args:
      cache: no
      force_rm: yes
      format: oci
      annotation:
        app: nginx
        function: proxy
        info: Load balancer for my cool app

- name: Build a Docker image
  podman_image:
    name: nginx
    path: /path/to/build/dir
    build_args:
      format: docker

- name: Build and push an image using existing credentials
  podman_image:
    name: nginx
    path: /path/to/build/dir
    push: yes
    push_args:
      dest: quay.io/acme

- name: Build and push an image using an auth file
  podman_image:
    name: nginx
    push: yes
    auth_file: /etc/containers/auth.json
    push_args:
      dest: quay.io/acme

- name: Build and push an image using username and password
  podman_image:
    name: nginx
    push: yes
    username: bugs
    password: "{{ vault_registry_password }}"
    push_args:
      dest: quay.io/acme

- name: Build and push an image to mulitple registries
  podman_image:
    name: "{{ item }}"
    path: /path/to/build/dir
    push: yes
    auth_file: /etc/containers/auth.json
  loop:
    - quay.io/acme/nginx
    - docker.io/acme/nginx

- name: Build and push an image to mulitple registries with separate parameters
  podman_image:
    name: "{{ item.name }}"
    tag: "{{ item.tag }}"
    path: /path/to/build/dir
    push: yes
    auth_file: /etc/containers/auth.json
    push_args:
      dest: "{{ item.dest }}"
  loop:
    - name: nginx
      tag: 4
      dest: docker.io/acme

    - name: nginx
      tag: 3
      dest: docker.io/acme


"""

RETURN = """
image:
  description:
    - Image inspection results for the image that was pulled, pushed, or built.
  returned: success
  type: dict
  sample:
{
    "actions": [
        "Built image myimage:latest from /root/build",
        "Pushed image myimage:latest to docker.io/acme"
    ],
    "changed": true,
    "image": [
        {
            "Annotations": {
                "app": "nginx",
                "function": "proxy",
                "info": "Load balancer for my cool app"
            },
            "Architecture": "amd64",
            "Author": "",
            "Comment": "",
            "ContainerConfig": {
                "Cmd": [
                    "/bin/bash"
                ],
                "Env": [
                    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/s\
bin:/bin"
                ],
                "Labels": {
                    "org.label-schema.build-date": "20181006",
                    "org.label-schema.license": "GPLv2",
                    "org.label-schema.name": "CentOS Base Image",
                    "org.label-schema.schema-version": "1.0",
                    "org.label-schema.vendor": "CentOS"
                }
            },
            "Created": "2018-10-26T16:33:44.983831874Z",
            "Digest": "sha256:f1a93c1ca2fd628f5aec74e67aab7b1876831f3e472c0180\
1ef29d02d8285ee7",
            "GraphDriver": {
                "Data": {
                    "LowerDir": "/var/lib/containers/storage/overlay/632dbad27\
7b565b77bdc9164d722ee7a10b692a7ca972b58d9d02e730f576517/diff:/var/lib/containe\
rs/storage/overlay/b21a503efb4ab61e34db1a5d4131de092449809ff010792fe523ea49831\
55c20/diff:/var/lib/containers/storage/overlay/f972d139738dfcd1519fd2461815651\
36ee25a8b54c358834c50af094bb262f/diff",
                    "MergedDir": "/var/lib/containers/storage/overlay/f41d3afa\
8b49b64e48fc37944f12a27d35271d666bcbde6dc9c2cca1bb88cdba/merged",
                    "UpperDir": "/var/lib/containers/storage/overlay/f41d3afa8\
b49b64e48fc37944f12a27d35271d666bcbde6dc9c2cca1bb88cdba/diff",
                    "WorkDir": "/var/lib/containers/storage/overlay/f41d3afa8b\
49b64e48fc37944f12a27d35271d666bcbde6dc9c2cca1bb88cdba/work"
                },
                "Name": "overlay"
            },
            "Id": "ba719f232d43f2f31c9c804859dd14ca2fbc0df80fa2bf3c43ca2728dcf\
5e29e",
            "Labels": {
                "org.label-schema.build-date": "20181006",
                "org.label-schema.license": "GPLv2",
                "org.label-schema.name": "CentOS Base Image",
                "org.label-schema.schema-version": "1.0",
                "org.label-schema.vendor": "CentOS"
            },
            "ManifestType": "application/vnd.oci.image.manifest.v1+json",
            "Os": "linux",
            "Parent": "",
            "RepoDigests": [
                "localhost/myimage@sha256:f1a93c1ca2fd628f5aec74e67aab7b187683\
1f3e472c01801ef29d02d8285ee7"
            ],
            "RepoTags": [
                "localhost/myimage:latest"
            ],
            "RootFS": {
                "Layers": [
                    "sha256:f972d139738dfcd1519fd2461815651336ee25a8b54c358834\
c50af094bb262f",
                    "sha256:ffcdc41a923a341055073f18c9acc5ad5dd1214ac2a1763272\
d37a5f0dbab7ea",
                    "sha256:703ad93ff2aa20b9c28203935a337a5ee4969d46b9de212ac6\
f17bacfbe21379",
                    "sha256:2054721e6c61d4f4ef13726126737038cc72cd7ae6c83da0ea\
1cd73fb8595140"
                ],
                "Type": "layers"
            },
            "Size": 208823219,
            "User": "",
            "Version": "",
            "VirtualSize": 208823219
        }
    ]
}
"""


class PodmanImageManager(object):

    def __init__(self, module, results):

        super(PodmanImageManager, self).__init__()

        self.module = module
        self.results = results
        self.name = self.module.params.get('name')
        self.executable = \
            self.module.get_bin_path(module.params.get('executable'),
                                     required=True)
        self.tag = self.module.params.get('tag')
        self.pull = self.module.params.get('pull')
        self.push = self.module.params.get('push')
        self.path = self.module.params.get('path')
        self.force = self.module.params.get('force')
        self.state = self.module.params.get('state')
        self.tls_verify = self.module.params.get('tls_verify')
        self.auth_file = self.module.params.get('auth_file')
        self.username = self.module.params.get('username')
        self.password = self.module.params.get('password')
        self.cert_dir = self.module.params.get('cert_dir')
        self.build_args = self.module.params.get('build_args')
        self.push_args = self.module.params.get('push_args')

        repo, repo_tag = parse_repository_tag(self.name)
        if repo_tag:
            self.name = repo
            self.tag = repo_tag

        self.image_name = '{name}:{tag}'.format(name=self.name, tag=self.tag)

        if self.state in ['present', 'build']:
            self.present()

        if self.state in ['absent']:
            self.absent()

    def _run(self, args, expected_rc=0, ignore_errors=False):
        if not isinstance(self.executable, list):
            command = [self.executable]
        command.extend(args)
        rc, out, err = self.module.run_command(command)
        if not ignore_errors and rc != expected_rc:
            self.module.fail_json(msg='Failed to run {command} {err}'.format(
                command=command, err=err))
        return rc, out, err

    def _get_id_from_output(self, lines, startswith=None, contains=None,
                            split_on=' ', maxsplit=1):
        layer_ids = []
        for line in lines.splitlines():
            _condition1 = (startswith and line.startswith(startswith))
            _condition2 = (contains and contains in line)
            if _condition1 or _condition2:
                splitline = line.rsplit(split_on, maxsplit)
                layer_ids.append(splitline[1])

        return(layer_ids[-1])

    def present(self):
        image = self.find_image()

        if not image or self.force:
            if self.path:
                # Build the image
                self.results['actions'].append(
                    'Built image {image_name} from {path}'.format(
                        image_name=self.image_name, path=self.path))
                self.results['changed'] = True
                if not self.module.check_mode:
                    self.results['image'] = self.build_image()
            else:
                # Pull the image
                self.results['actions'].append(
                    'Pulled image {image_name}'.format(
                        image_name=self.image_name))
                self.results['changed'] = True
                if not self.module.check_mode:
                    self.results['image'] = self.pull_image()

        if self.push:
            # Push the image
            if '/' in self.image_name:
                push_format_string = 'Pushed image {image_name}'
            else:
                push_format_string = 'Pushed image {image_name} to {dest}'
            self.results['actions'].append(
                push_format_string.format(
                    image_name=self.image_name,
                    dest=self.push_args['dest']))
            self.results['changed'] = True
            if not self.module.check_mode:
                self.results['image'] = self.push_image()

    def absent(self):
        image = self.find_image()

        if image:
            self.results['actions'].append(
                'Removed image {name}'.format(name=self.name))
            self.results['changed'] = True
            self.results['image']['state'] = 'Deleted'
            if not self.module.check_mode:
                self.remove_image()

    def find_image(self, image_name=None):
        if image_name is None:
            image_name = self.image_name
        args = ['image', 'ls', image_name, '--format', 'json']
        rc, images, err = self._run(args, ignore_errors=True)
        if len(images) > 0:
            return json.loads(images)
        else:
            return None

    def inspect_image(self, image_name=None):
        if image_name is None:
            image_name = self.image_name
        args = ['inspect', image_name, '--format', 'json']
        rc, image_data, err = self._run(args)
        if len(image_data) > 0:
            return json.loads(image_data)
        else:
            return None

    def pull_image(self, image_name=None):
        if image_name is None:
            image_name = self.image_name

        args = ['pull', image_name, '-q']

        if self.auth_file:
            args.extend(['--authfile', self.auth_file])

        if self.tls_verify:
            args.append('--tls-verify')

        if self.cert_dir:
            args.extend(['--cert-dir', self.cert_dir])

        rc, out, err = self._run(args, ignore_errors=True)
        if rc != 0:
            self.module.fail_json(
                msg='Failed to pull image {image_name}'.format(
                    image_name=image_name))
        return self.inspect_image(out.strip())

    def build_image(self):
        args = ['build', '-q']
        args.extend(['-t', self.image_name])

        if self.tls_verify:
            args.append('--tls-verify')

        annotation = self.build_args.get('annotation')
        if annotation:
            for k, v in annotation.items():
                args.extend(['--annotation', '{k}={v}'.format(k=k, v=v)])

        if self.cert_dir:
            args.extend(['--cert-dir', self.cert_dir])

        if self.build_args.get('force_rm'):
            args.append('--force-rm')

        image_format = self.build_args.get('format')
        if image_format:
            args.extend(['--format', image_format])

        if not self.build_args.get('cache'):
            args.append('--no-cache')

        if self.build_args.get('rm'):
            args.append('--rm')

        volume = self.build_args.get('volume')
        if volume:
            for v in volume:
                args.extend(['--volume', v])

        if self.auth_file:
            args.extend(['--authfile', self.auth_file])

        if self.username and self.password:
            cred_string = '{user}:{password}'.format(user=self.username,
                                                     password=self.password)
            args.extend(['--creds', cred_string])

        args.append(self.path)

        rc, out, err = self._run(args, ignore_errors=True)
        if rc != 0:
            self.module.fail_json(
                msg="Failed to build image {image}: {out} {err}".format(
                    image=self.image_name,
                    out=out,
                    err=err))

        last_id = self._get_id_from_output(out, startswith='-->')
        return self.inspect_image(last_id)

    def push_image(self):
        args = ['push']

        if self.tls_verify:
            args.append('--tls-verify')

        if self.cert_dir:
            args.extend(['--cert-dir', self.cert_dir])

        if self.username and self.password:
            cred_string = '{user}:{password}'.format(user=self.username,
                                                     password=self.password)
            args.extend(['--creds', cred_string])

        if self.auth_file:
            args.extend(['--authfile', self.auth_file])

        if self.push_args.get('compress'):
            args.append('--compress')

        push_format = self.push_args.get('format')
        if push_format:
            args.extend(['--format', push_format])

        if self.push_args.get('remove_signatures'):
            args.append('--remove_signatures')

        sign_by_key = self.push_args.get('sign_by')
        if sign_by_key:
            args.extend(['--sign-by', sign_by_key])

        args.append(self.image_name)

        # Build the destination argument
        dest = self.push_args.get('dest')
        dest_format_string = '{dest}/{image_name}'
        regexp = re.compile(r'/{name}(:{tag})?'.format(
            name=self.name,
            tag=self.tag))
        if not dest:
            if '/' not in self.name:
                self.module.fail_json(
                    msg="'push_args['dest']' is required when pushing images "
                        "that do not have the remote registry in the "
                        "image name")

        # If the push destinaton contains the image name and/or the tag
        # remove it and warn since it's not needed.
        elif regexp.search(dest):
            dest = regexp.sub('', dest)
            self.module.warn(
                "Image name and tag are automatically added to "
                "push_args['dest']. Destination changed to {dest}".format(
                    dest=dest))

        if dest and dest.endswith('/'):
            dest = dest[:-1]

        transport = self.push_args.get('transport')
        if transport:
            if not dest:
                self.module.fail_json(
                    "'push_args['transport'] requires 'push_args['dest'] but "
                    "it was not provided.")
            if transport == 'docker':
                dest_format_string = '{transport}://{dest}'
            elif transport == 'ostree':
                dest_format_string = '{transport}:{name}@{dest}'
            else:
                dest_format_string = '{transport}:{dest}'

        dest_string = dest_format_string.format(transport=transport,
                                                name=self.name,
                                                dest=dest,
                                                image_name=self.image_name,)

        # Only append the destination argument if the image name is not a URL
        if '/' not in self.name:
            args.append(dest_string)

        rc, out, err = self._run(args, ignore_errors=True)
        if rc != 0:
            self.module.fail_json(
                msg="Failed to push image {image_name}: {err}".format(
                    image_name=self.image_name,
                    err=err,
                    )
                )
        last_id = self._get_id_from_output(
            out + err, contains=':', split_on=':')

        return self.inspect_image(last_id)

    def remove_image(self, image_name=None):
        if image_name is None:
            image_name = self.image_name

        args = ['rmi', image_name]
        if self.force:
            args.append('--force')
        rc, out, err = self._run(args, ignore_errors=True)
        if rc != 0:
            self.module.fail_json(
                msg='Failed to remove image {image_name}. {err}'.format(
                    image_name=image_name, err=err))
        return out


def parse_repository_tag(repo_name):
    parts = repo_name.rsplit('@', 1)
    if len(parts) == 2:
        return tuple(parts)
    parts = repo_name.rsplit(':', 1)
    if len(parts) == 2 and '/' not in parts[1]:
        return tuple(parts)
    return repo_name, None


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            tag=dict(type='str', default='latest'),
            pull=dict(type='bool', default=True),
            push=dict(type='bool', default=False),
            path=dict(type='str'),
            force=dict(type='bool', default=False),
            state=dict(
                type='str',
                default='present',
                choices=['absent', 'present', 'build']
            ),
            tls_verify=dict(type='bool', default=True, aliases=['tlsverify']),
            executable=dict(type='str', default='podman'),
            auth_file=dict(type='path', aliases=['authfile']),
            username=dict(type='str'),
            password=dict(type='str', no_log=True),
            cert_dir=dict(type='path'),
            build_args=dict(
                type='dict',
                aliases=['buildargs'],
                default={},
                options=dict(
                    annotation=dict(type='dict'),
                    force_rm=dict(type='bool'),
                    format=dict(
                        type='str',
                        choices=['oci', 'docker'],
                        default='oci'
                    ),
                    cache=dict(type='bool', default=True),
                    rm=dict(type='bool', default=True),
                    volume=dict(type='list'),
                ),
            ),
            push_args=dict(
                type='dict',
                default={},
                options=dict(
                    compress=dict(type='bool'),
                    format=dict(type='str', choices=['oci', 'v2s1', 'v2s2']),
                    remove_signatures=dict(type='bool'),
                    sign_by=dict(type='str'),
                    dest=dict(type='str', aliases=['destination'],),
                    transport=dict(
                        type='str',
                        choices=[
                            'dir',
                            'docker-archive',
                            'docker-daemon',
                            'oci-archive',
                            'ostree',
                        ]
                    ),
                ),
            ),
        ),
        supports_check_mode=True,
        required_together=(
            ['username', 'password'],
        ),
        mutually_exclusive=(
            ['authfile', 'username'],
            ['authfile', 'password'],
        ),
    )

    results = dict(
        changed=False,
        actions=[],
        image={},
        )

    PodmanImageManager(module, results)
    module.exit_json(**results)


if __name__ == '__main__':
    main()
