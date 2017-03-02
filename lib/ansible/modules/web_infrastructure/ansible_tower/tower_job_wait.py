#!/usr/bin/python
#coding: utf-8 -*-

# (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

ANSIBLE_METADATA = {'status': ['preview'],
                    'supported_by': 'community',
                    'version': '1.0'}

DOCUMENTATION = '''
---
module: tower_job_wait
version_added: "2.3"
short_description: Wait for Ansible Tower job to finish.
description:
    - Wait for Ansible Tower job to finish and report success or failure. See
      U(https://www.ansible.com/tower) for an overview.
options:
    job_id:
      description:
        - ID of the job to monitor.
      required: True
    min_interval:
      description:
        - Minimum interval in seconds, to request an update from Tower.
      default: 1
    max_interval:
      description:
        - Maximum interval in seconds, to request an update from Tower.
      default: 30
    timeout:
      description:
        - Maximum time in seconds to wait for a job to finish.
      default: null
extends_documentation_fragment: tower
'''

EXAMPLES = '''
- name: Launch a job
  tower_job_launch:
    job_template: "My Job Template"
    register: job
- name: Wait for job max 120s
  tower_job_wait:
    job_id: job.id
    timeout: 120
'''

RETURN = '''
id:
    description: job id that is being waited on
    returned: success
    type: int
    sample: 99
elapsed:
    description: total time in seconds the job took to run
    returned: success
    type: float
    sample: 10.879
started:
    description: timestamp of when the job started running
    returned: success
    type: string
    sample: 2017-03-01T17:03:53.200234Z
finished:
    description: timestamp of when the job finished running
    returned: success
    type: string
    sample: 2017-03-01T17:04:04.078782Z
status:
    description: current status of job
    returned: success
    type: string
    sample: successful
'''


from ansible.module_utils.basic import AnsibleModule

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

try:
    import tower_cli
    import tower_cli.utils.exceptions as exc

    from tower_cli.conf import settings
    from ansible.module_utils.ansible_tower import (
        tower_auth_config,
        tower_check_mode,
        tower_argument_spec,
    )

    HAS_TOWER_CLI = True
except ImportError:
    HAS_TOWER_CLI = False


def main():
    argument_spec = tower_argument_spec()
    argument_spec.update(dict(
        job_id = dict(type='int', required=True),
        timeout = dict(type='int'),
        min_interval = dict(type='float', default=1),
        max_interval = dict(type='float', default=30),
    ))

    module = AnsibleModule(
        argument_spec,
        supports_check_mode=True
    )

    if not HAS_TOWER_CLI:
        module.fail_json(msg='ansible-tower-cli required for this module')

    json_output = {}
    fail_json = None

    tower_auth = tower_auth_config(module)
    with settings.runtime_values(**tower_auth):
        tower_check_mode(module)
        job = tower_cli.get_resource('job')
        params = module.params.copy()

        # tower-cli gets very noisy when monitoring.
        # We pass in our our outfile to supress the out during our monitor call.
        outfile = StringIO()
        params['outfile'] = outfile

        job_id = params.get('job_id')
        try:
            result = job.monitor(job_id, **params)
        except exc.Timeout as excinfo:
            result = job.status(job_id)
            result['id'] = job_id
            json_output['msg'] = 'Timeout waiting for job to finish.'
            json_output['timeout'] = True
        except exc.NotFound as excinfo:
            fail_json = dict(msg='Unable to wait, no job_id {0} found: {1}'.format(job_id, excinfo), changed=False)
        except (exc.ConnectionError, exc.BadRequest) as excinfo:
            fail_json = dict(msg='Unable to wait for job: {0}'.format(excinfo), changed=False)

    if fail_json is not None:
        module.fail_json(**fail_json)

    json_output['success'] = True
    for k in ('id', 'status', 'elapsed', 'started', 'finished'):
        json_output[k] = result.get(k)

    module.exit_json(**json_output)


if __name__ == '__main__':
    main()
