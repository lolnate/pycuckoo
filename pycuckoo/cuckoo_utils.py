import json
import logging
import os
import re
import shutil
import time
import tarfile
import zipfile

from pycuckoo.cuckooapi import CuckooAPI


class CuckooUtils():

    def __init__(self, baseurl, apikey='', proxies={}, verify=True):
        self.baseurl = baseurl
        if self.baseurl[-1] == '/':
            self.baseurl = self.baseurl[:-1]
        self.apikey = apikey
        self.proxies = proxies
        self.verify = verify
        self.log = logging.getLogger()
        self.cuckoo = CuckooAPI(self.baseurl, proxies=proxies, verify=verify)

    def set_proxy(self, http, https):
        self.proxies = {
            'http': http,
            'https': https,
        }
        self.cuckoo.set_proxy(http, https)

    def track_task_until_completed(self, task_id):
        status = ''
        last_status = ''
        while status != 'reported':
            status = self.cuckoo.get_task_status(task_id)
            if status != last_status:
                self.log.info('Status changed to {0}'.format(status))
                last_status = status
            if status == 'error':
                return False
            if status != 'reported':
                time.sleep(2)
        return True

    def download_results(self, target_dir, task_id):
        # Delete the directory first
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        self.log.info('Downloading json report for task_id '
                      '{0}'.format(task_id))
        report = self.cuckoo.get_task_report(task_id)
        if not report:
            self.log.error('No report found when downloading results for '
                           'task_id {0}'.format(task_id))
        # We want to save a report as report_X.json depending on how many
        # reports exist
        report_num = 0
        report_path = os.path.join(target_dir,
                                   'report_{0}.json'.format(report_num))
        while os.path.exists(report_path):
            report_num += 1
        with open(report_path, 'w') as fp:
            json.dump(report, fp, indent=2)

        self.log.info('Downloading procmemory for task_id {0}'.format(task_id))
        memory_dir = os.path.join(target_dir, 'memory')
        result = self.cuckoo.get_task_procmemory(task_id, memory_dir)
        # If everything was correct, now we are going to extract the .tar.bz2
        # if result:
        #    self._extract_cuckoo_tarbz2_archive(memory_bz2_file, memory_dir)
        #    self.log.info('Finished downloading procmemory for task_id '
        #                  '{0}'.format(task_id))

        self.log.info('Downloading dropped files for task_id '
                      '{0}'.format(task_id))
        dropped_files_bz2 = os.path.join(target_dir,
                                         'dropped',
                                         'dropped.tar.bz2')
        dropped_dir = os.path.join(target_dir, 'dropped')
        result = self.cuckoo.get_task_dropped_files(task_id, dropped_files_bz2)
        if result:
            self._extract_cuckoo_tarbz2_archive(dropped_files_bz2, dropped_dir)
            self.log.info('Finished downloading dropped files for task_id '
                          '{0}'.format(task_id))

    def _extract_cuckoo_tarbz2_archive(self, archive_path, target_path):
        """
        Extracts the archive provided into target_path and first level .zip
        files. Removes any the tarbz2 and the first level zips.

        :param archive_path: the .tar.bz2  archive to extract
        :param target_path: the location to extract the files
        """
        # Now let's try to extract it as a bz2 archive
        try:
            first_level_zips = []
            re_dmp = re.compile(r'([0-9a-zA-Z.]+)\.zip')
            tar_archive = tarfile.open(name=archive_path)
            tar_archive.extractall(path=target_path)
            tar_archive.close()
            for zipped_file in os.listdir(target_path):
                zip_match = re_dmp.match(zipped_file)
                if zip_match:
                    self.log.info('Writing file {}'.format(zip_match.group(0)))
                    first_level_zips.append(zipped_file)
                    # Now we unzip the file to the target_path
                    zip_ref = zipfile.ZipFile(os.path.join(target_path,
                                                           zipped_file), 'r')
                    zip_ref.extractall(target_path)
                    zip_ref.close()

            # Now we can remove all the .zip and .tar.bz2 archives so we don't
            # waste space
            for zip_remove in first_level_zips:
                os.remove(zip_remove)
            os.remove(archive_path)

        except Exception as e:
            self.log.warning('Problem extracting archives for the '
                             'file {0}. Error: {1}'.format(archive_path, e))

    def get_all_valid_tags(self):
        """
        Returns all valid tags from all available cuckoo machines

        :returns: set() - all valid tags
        """
        machines_list = self.cuckoo.get_machines_list()
        valid_tags = set()
        if 'data' not in machines_list:
            return None
        for machine in machines_list['data']:
            if 'tags' in machine:
                for tag in machine['tags']:
                    valid_tags.add(tag)
        return valid_tags
