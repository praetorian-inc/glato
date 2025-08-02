from urllib.parse import quote


class Project:
    def __init__(self, project_path, api):
        self.api = api
        self.project = self._get_project(project_path)
        self.id = self.project['id']

    def _get_project(self, project_path):
        encoded_path = project_path.replace('/', '%2F').lstrip('%2F')
        endpoint = f'/projects/{encoded_path}'
        response = self.api._call_get(endpoint, cache_response=False)
        return response.json()

    def create_branch(self,
                      branch='glato-test'
                      ):
        endpoint = f'/projects/{self.id}/repository/branches'
        json = {
            'branch': branch,
            'ref': self.project['default_branch']
        }
        response = self.api._call_post(endpoint, json)
        if response.status_code == 400:
            # branch already exists
            print("Branch already exists. Replacing YML file on pre-existing branch.")
            return True, False
        if response.status_code == 201:
            # branch created successfully
            print("New branch created successfully.")
            return True, True
        else:
            # error
            return False, False

    def delete_branch(self,
                      branch='glato-test'
                      ):
        endpoint = f'/projects/{self.id}/repository/branches/{branch}'
        response = self.api._call_delete(endpoint)
        if response.status_code == 204:
            print("Branch deleted successfully")
        else:
            print("Error deleting branch")

    def get_pipelines(self):
        endpoint = f'/projects/{self.id}/pipelines'
        response = self.api._call_get(endpoint)
        return response.json()

    def get_pipelines_by(self, params):
        endpoint = f'/projects/{self.id}/pipelines'
        response = self.api._call_get(endpoint, params)
        return response.json()

    def delete_pipeline(self, pipeline_id):
        endpoint = f'/projects/{self.id}/pipelines/{pipeline_id}'
        response = self.api._call_delete(endpoint)
        if response.status_code == 204:
            print("Pipeline logs deleted successfully")
        else:
            print("Error deleting pipeline logs")

    def get_latest_pipeline(self, ref='main'):
        endpoint = f'/projects/{self.id}/pipelines/latest'
        params = {
            'ref': ref
        }
        response = self.api._call_get(
            endpoint, params=params, cache_response=False)
        return response.json()

    def create_commit(self, branch, actions, msg='Quick edit'):
        endpoint = f'/projects/{self.id}/repository/commits'
        json = {
            'branch': branch,
            'commit_message': msg,
            'actions': actions
        }
        response = self.api._call_post(endpoint, json)
        if response.status_code == 201:
            print("Successfully pushed commit")
            return True
        else:
            print("Commit Failed. Possible Error Occured.")
            return False

    def get_pipeline_jobs(self, pipeline_id):
        endpoint = f'/projects/{self.id}/pipelines/{pipeline_id}/jobs'
        response = self.api._call_get(endpoint, cache_response=False)
        return response.json()

    def get_job_log(self, job_id):
        endpoint = f'/projects/{self.id}/jobs/{job_id}/trace'
        response = self.api._call_get(endpoint, cache_response=False)
        return response.text
