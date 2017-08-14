import json
import logging
import os
import requests


class CuckooAPI():

    def __init__(self, baseurl, apikey='', proxies={}, verify=True):
        self.baseurl = baseurl
        if self.baseurl[-1] == '/':
            self.baseurl = self.baseurl[:-1]
        self.apikey = apikey
        self.proxies = proxies
        self.verify = verify
        self.log = logging.getLogger()

    def set_proxy(self, http, https):
        self.proxies = {
            'http': http,
            'https': https,
        }

    def get_task_ids(self, md5):
        """
        Searches for a sample with the given MD5 and returns the tasks
        associated with that sample.

        Args:
            md5: The md5 of the sample

        Returns:
            A list with the task_ids found for that sample
        """
        search_url = '{0}/tasks/list'.format(self.baseurl, md5)
        response = self.get_request(search_url)
        task_ids = []
        if 'tasks' in response:
            for task in response['tasks']:
                if 'sample' in task:
                    if task['sample']['md5'] == md5:
                        task_ids.append(task['guest']['task_id'])
        return task_ids

    def get_task_status(self, task_id):
        search_url = '{0}/tasks/view/{1}'.format(self.baseurl, task_id)
        response = self.get_request(search_url)
        if response:
            if 'task' in response:
                return response['task']['status']
        return None

    def get_task_report(self, task_id):
        self.log.debug('Downloading report for task_id {0}'.format(task_id))
        search_url = '{0}/tasks/report/{1}'.format(self.baseurl, task_id)
        response = self.get_request(search_url)
        if response:
            return response
        self.log.warning('No report received for task_id {0}'.format(task_id))
        return None

    def get_task_procmemory(self, task_id, filepath):
        """
        Download process memory. Cuckoo returns a .tar.bz2 archive of all the
        process memory.
        :param task_id: The task_id in cuckoo to download the process memory
        :param filepath: The file path to save the .tar.bz2
        """
        basepath = os.path.dirname(filepath)
        if not os.path.exists(basepath):
            self.log.debug('Creating directory {0}'.format(basepath))
            os.makedirs(basepath)
        self.log.debug('Download processing memory for task_id '
                       '{0}'.format(task_id))
        # First we need to get a list of our memory available.
        search_url = '{0}/memory/list/{1}'.format(self.baseurl, task_id)
        list_request = self.get_request(search_url)
        processes_with_memory = []
        if list_request is None:
            return False
        if 'dump_files' in list_request:
            for dump_file in list_request['dump_files']:
                # Format is like: 2656-7e47a23408e3606e.dll_
                processes_with_memory.append(dump_file.split('-')[0])
        else:
            return False
        # Now we can download each process memory
        processes_with_memory = set(processes_with_memory)
        for process in processes_with_memory:
            procmem_url = '{0}/memory/get/{1}/{2}'.format(self.baseurl,
                                                          task_id, process)
            raw_response = self.get_raw_request(procmem_url, stream=True)
            if not raw_response:
                return False
            try:
                self.log.debug('Writing procmemory to disk for task_id '
                               '{0} and process {1}.'.format(task_id, process))
                with open(filepath, "wb") as fp:
                    for chunk in raw_response.iter_content(chunk_size=1024):
                        if chunk:
                            fp.write(chunk)
            except Exception as e:
                self.log.error('Error downloading process memory archives for '
                               'task_id {0}. Error: {1}'.format(task_id, e))
                return False
        return True

    def get_task_dropped_files(self, task_id, filepath):
        """
        Download dropped files. Cuckoo returns a .tar.bz2 archive of all the
        dropped files during sample execution.
        :param task_id: The task_id in cuckoo to download the dropped files
        :param filepath: The file path to save the .tar.bz2
        """
        basepath = os.path.dirname(filepath)
        if not os.path.exists(basepath):
            self.log.debug('Creating directory {0}'.format(basepath))
            os.makedirs(basepath)
        self.log.debug('Downloading dropped files for task_id '
                       '{0}'.format(task_id))
        # First we need to get a list of all the dropped files
        search_url = '{0}/tasks/report/{1}/dropped'.format(self.baseurl,
                                                           task_id)
        raw_response = self.get_raw_request(search_url, stream=True)
        try:
            self.log.debug('Writing dropped files to disk for task_id '
                           '{0}.'.format(task_id))
            with open(filepath, "wb") as fp:
                for chunk in raw_response.iter_content(chunk_size=1024):
                    if chunk:
                        fp.write(chunk)
        except Exception as e:
            self.log.error('Error downloading dropped files archives for '
                           'task_id {0}. Error: {1}'.format(task_id, e))
            return False
        return True

    def get_machines_list(self):
        """
        Gathers list of all machines available.

        :returns: Generator, dict (using json.loads())
        """
        url = '{0}/machines/list/'.format(self.baseurl)
        response = self.get_request(url)
        return response

    def submit_new_file(self, filepath, tags=[]):
        """
        Submits the given file path to cuckoo with the provided conditions.
        :param filepath:
        :param tags:
        :return:
        """
        with open(filepath, 'rb') as sample:
            fname = os.path.basename(filepath)
            mp_file = {'file': (fname, sample)}
            self.log.debug('Creating task for tags: {}'.format(','.join(tags)))
            # Cuckoo expects a comma separated list of tags
            data = {}
            data['options'] = ''
            if len(tags) > 0:
                data['tags'] = ','.join(tags)
            r = requests.post("{0}/tasks/create/file".format(self.baseurl),
                              files=mp_file,
                              data=data,
                              proxies=self.proxies,
                              verify=self.verify)

        if r.status_code != 200:
            self.log.error('File submission to cuckoo failed for file '
                           '{0}'.format(filepath))
            self.log.error('Status code was: {0}'.format(r.status_code))
            self.log.error('Object was: {0}'.format(repr(r)))
            return []

        # Add the sample to the files this worker is tracking.
        json_decoder = json.JSONDecoder()
        response = json_decoder.decode(r.text)
        if 'error' in response:
            if response['error']:
                self.log.error('Error received when creating a new task for '
                               'file {0}. Error: '
                               '{1}'.format(filepath,
                                            response['error_value']))
                return []

        if response['task_id'] is None:
            self.log.error('Received no task_ids when submitting the file '
                           '{0}'.format(filepath))
            return []

        self.log.info('{0} submitted to Cuckoo successfully.'.format(filepath))
        # TODO: This is hacky for now, but I believe we may want to submit
        # multiple files in the future in this function?
        return [response['task_id']]

    def get_request(self, url, **kwargs):
        self.log.debug('GET Request: {0}'.format(url))
        r = requests.get(url, kwargs, proxies=self.proxies, verify=self.verify)
        if r.status_code == 200:
            json_decoder = json.JSONDecoder()
            try:
                j = json_decoder.decode(r.text)
                return j
            except IndexError as e:
                self.log.error('IndexError caught when decoding JSON'
                               ' response.')
                self.log.error('Error was: {}'.format(e))
                self.log.debug('Response text was: {}'.format(r.text))
                return None
        else:
            self.log.error('Received a non-200 ({0}) for the GET request: '
                           '{1}'.format(r.status_code, url))
            return None

    def get_raw_request(self, url, **kwargs):
        self.log.debug('GET Request: {0}'.format(url))
        r = requests.get(url, kwargs, proxies=self.proxies, verify=self.verify)
        if r.status_code == 200:
            return r
        else:
            self.log.error('Received a non-200 ({0}) for the GET request: '
                           '{1}'.format(r.status_code, url))
            return None
