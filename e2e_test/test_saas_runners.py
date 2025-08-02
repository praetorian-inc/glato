"""
End-to-end tests for GitLab SaaS Runner functionality.

This module tests runner functionality specifically on GitLab SaaS,
focusing on SaaS-specific runner configurations and behaviors.
"""

import os
import requests
import time
import pytest
import urllib.parse
import uuid
from pathlib import Path
from git import Repo
import json


class TestSaaSRunners:
    """GitLab Runner tests specifically for SaaS environments."""
    
    @pytest.fixture(autouse=True)
    def setup(self, gitlab_url, tokens):
        """Set up test environment for SaaS testing."""
        self.gitlab_url = gitlab_url
        
        # SaaS token configuration
        self.token = (
            tokens.get('SAAS_ALICE_TOKEN') or 
            tokens.get('SAAS_ADMIN_TOKEN') or
            os.getenv("SAAS_ALICE_TOKEN") or
            os.getenv("SAAS_ADMIN_TOKEN") or
            os.getenv("ALICE_GLATO_TOKEN") or
            os.getenv("GITLAB_ADMIN_TOKEN")
        )
        assert self.token, "SaaS token required. Set SAAS_ALICE_TOKEN or SAAS_ADMIN_TOKEN"
        
        # SaaS project configuration
        self.project_path = "product-glato/api-glato/api-service-glato"
        self.project_id = "70224558"
        self.group_id = "108253043"
        
        # Set up headers for SaaS
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Generate unique test ID for isolation
        self.test_id = str(uuid.uuid4())[:8]
        
        print(f"🔧 Setup complete for SaaS project {self.project_id} (test ID: {self.test_id})")

    def test_runners_are_online(self):
        """Test that required runners are online and properly configured on SaaS."""
        print("🔍 Testing SaaS runner availability...")
        
        # Check project runners
        response = requests.get(
            f"{self.gitlab_url}/api/v4/projects/{self.project_id}/runners",
            headers=self.headers,
            verify=False
        )
        assert response.status_code == 200, f"Failed to get project runners: {response.status_code}"
        
        project_runners = response.json()
        
        # SaaS should have both project and group runners
        project_type_runners = [r for r in project_runners if r.get("runner_type") == "project_type"]
        group_type_runners = [r for r in project_runners if r.get("runner_type") == "group_type"]
        
        assert len(project_type_runners) >= 1, "At least 1 project runner should be available on SaaS"
        assert len(group_type_runners) >= 1, "At least 1 group runner should be available on SaaS"
        
        # Verify all runners are online
        for runner in project_runners:
            assert runner["status"] == "online", f"Runner {runner['id']} is not online: {runner['status']}"
            assert runner["active"] is True, f"Runner {runner['id']} is not active"
        
        print(f"✅ SaaS runners online:")
        for runner in project_runners:
            print(f"   Runner #{runner['id']}: {runner['runner_type']} - {runner['status']}")

    def test_project_runner_execution(self):
        """Test project runner job execution on SaaS."""
        print("🚀 Testing SaaS project runner job execution...")
        
        # Wait to avoid conflicts from previous tests
        time.sleep(10)
        
        config = f"""stages:
  - test

project_runner_test_{self.test_id}:
  stage: test
  image: ubuntu:22.04
  script:
    - echo Project runner test {self.test_id}
    - echo Environment SaaS
    - echo Timestamp $(date)
    - sleep 2
    - echo Project runner test complete
"""
        
        pipeline_id = self._create_and_wait_for_pipeline(
            config, 
            f"Test SaaS project runner {self.test_id}",
            timeout=120
        )
        
        jobs = self._get_pipeline_jobs(pipeline_id)
        assert len(jobs) == 1, f"Expected 1 job, got {len(jobs)}"
        
        job = jobs[0]
        
        if job['status'] != 'success':
            print(f"❌ Job failed. Details: {job}")
            self._debug_failed_job(job)
        
        assert job["status"] == "success", f"Job should succeed, got: {job['status']}"
        
        runner = job.get("runner", {})
        runner_type = runner.get("runner_type")
        assert runner_type in ["project_type", "group_type"], f"Should use project or group runner, got: {runner_type}"
        
        print("✅ SaaS project runner execution successful")

    def test_group_runner_execution(self):
        """Test group runner job execution on SaaS."""
        print("🚀 Testing SaaS group runner job execution...")
        
        # Wait to avoid conflicts
        time.sleep(10)
        
        config = f"""stages:
  - test

group_runner_test_{self.test_id}:
  stage: test
  image: ubuntu:22.04
  script:
    - echo Group runner test {self.test_id}
    - echo Environment SaaS
    - echo Timestamp $(date)
    - sleep 2
    - echo Group runner test complete
"""
        
        pipeline_id = self._create_and_wait_for_pipeline(
            config, 
            f"Test SaaS group runner {self.test_id}",
            timeout=120
        )
        
        jobs = self._get_pipeline_jobs(pipeline_id)
        assert len(jobs) == 1, f"Expected 1 job, got {len(jobs)}"
        
        job = jobs[0]
        
        if job['status'] != 'success':
            print(f"❌ Job failed. Details: {job}")
            self._debug_failed_job(job)
        
        assert job["status"] == "success", f"Job should succeed, got: {job['status']}"
        
        runner = job.get("runner", {})
        runner_type = runner.get("runner_type")
        assert runner_type in ["project_type", "group_type"], f"Should use project or group runner, got: {runner_type}"
        
        print("✅ SaaS group runner execution successful")

    def test_parallel_runner_execution(self):
        """Test parallel runner job execution on SaaS."""
        print("🚀 Testing SaaS parallel runner execution...")
        
        # Wait to avoid conflicts
        time.sleep(15)
        
        config = f"""
stages:
  - test

parallel_project_test_{self.test_id}:
  stage: test
  image: ubuntu:22.04
  script:
    - echo Parallel project test {self.test_id}
    - echo Environment SaaS
    - echo Job """ + "${CI_JOB_NAME}" + f"""
    - sleep 3
    - echo Parallel project test complete
  parallel: 2

parallel_group_test_{self.test_id}:
  stage: test
  image: ubuntu:22.04
  script:
    - echo Parallel group test {self.test_id}
    - echo Environment SaaS
    - echo Job """ + "${CI_JOB_NAME}" + f"""
    - sleep 3
    - echo Parallel group test complete
  parallel: 2
"""
        
        pipeline_id = self._create_and_wait_for_pipeline(
            config, 
            f"Test SaaS parallel runners {self.test_id}",
            timeout=180
        )
        
        jobs = self._get_pipeline_jobs(pipeline_id)
        assert len(jobs) == 4, f"Expected 4 jobs (2 project + 2 group), got {len(jobs)}"
        
        # Verify all jobs succeeded
        for job in jobs:
            if job['status'] != 'success':
                print(f"❌ Job {job['name']} failed. Details: {job}")
                self._debug_failed_job(job)
            assert job["status"] == "success", f"Job {job['name']} should succeed, got: {job['status']}"
        
        # Verify runner type distribution - just ensure all jobs used available runners
        used_runners = [j.get("runner", {}).get("runner_type") for j in jobs]
        valid_runner_types = ["project_type", "group_type"]
        
        for i, runner_type in enumerate(used_runners):
            assert runner_type in valid_runner_types, f"Job {i+1} used invalid runner type: {runner_type}"
        
        print(f"✅ Used runners: {used_runners}")

    def _create_and_wait_for_pipeline(self, config: str, commit_message: str, timeout: int = 120) -> int:
        """Create a pipeline and wait for completion on SaaS."""
        print(f"📝 Creating pipeline: {commit_message}")
        
        # Create temporary directory for git operations
        temp_dir = Path("/tmp") / f"glato_test_{self.test_id}"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Clone the repository
            clone_url = f"https://oauth2:{self.token}@gitlab.com/{self.project_path}.git"
            repo = Repo.clone_from(clone_url, temp_dir)
            
            # Create unique branch
            branch_name = f"test-runner-{self.test_id}-{int(time.time())}"
            repo.git.checkout("-b", branch_name)
            
            # Write the GitLab CI config
            ci_file = temp_dir / ".gitlab-ci.yml"
            ci_file.write_text(config)
            
            # Commit and push
            repo.index.add([".gitlab-ci.yml"])
            repo.index.commit(commit_message)
            repo.git.push("origin", branch_name)
            
            # Get the pipeline ID
            time.sleep(5)  # Wait for pipeline creation
            
            response = requests.get(
                f"{self.gitlab_url}/api/v4/projects/{self.project_id}/pipelines",
                headers=self.headers,
                params={"ref": branch_name, "per_page": 1}
            )
            assert response.status_code == 200, f"Failed to get pipelines: {response.status_code}"
            
            pipelines = response.json()
            assert len(pipelines) > 0, "No pipeline found"
            
            pipeline_id = pipelines[0]["id"]
            print(f"📋 Pipeline created: {pipeline_id}")
            
            # Wait for pipeline completion
            start_time = time.time()
            while time.time() - start_time < timeout:
                response = requests.get(
                    f"{self.gitlab_url}/api/v4/projects/{self.project_id}/pipelines/{pipeline_id}",
                    headers=self.headers
                )
                assert response.status_code == 200, f"Failed to get pipeline status: {response.status_code}"
                
                pipeline = response.json()
                status = pipeline["status"]
                
                print(f"🔄 Pipeline {pipeline_id} status: {status}")
                
                if status in ["success", "failed", "canceled", "skipped"]:
                    if status != "success":
                        self._debug_failed_pipeline(pipeline_id)
                    return pipeline_id
                
                time.sleep(10)
            
            raise TimeoutError(f"Pipeline {pipeline_id} did not complete within {timeout} seconds")
            
        finally:
            # Cleanup
            try:
                if 'repo' in locals():
                    # Delete the test branch
                    repo.git.push("origin", f":{branch_name}")
            except Exception as e:
                print(f"⚠️ Cleanup warning: {e}")
            
            # Remove temp directory
            import shutil
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _get_pipeline_jobs(self, pipeline_id: int) -> list:
        """Get jobs for a pipeline on SaaS."""
        response = requests.get(
            f"{self.gitlab_url}/api/v4/projects/{self.project_id}/pipelines/{pipeline_id}/jobs",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get pipeline jobs: {response.status_code}"
        return response.json()

    def _debug_failed_job(self, job):
        """Debug a failed job on SaaS."""
        print(f"🔍 Debugging failed job {job['id']}: {job['name']}")
        
        # Get job trace
        response = requests.get(
            f"{self.gitlab_url}/api/v4/projects/{self.project_id}/jobs/{job['id']}/trace",
            headers=self.headers
        )
        if response.status_code == 200:
            print(f"📋 Job trace:\n{response.text}")
        else:
            print(f"❌ Could not get job trace: {response.status_code}")

    def _debug_failed_pipeline(self, pipeline_id):
        """Debug a failed pipeline on SaaS."""
        print(f"🔍 Debugging failed pipeline {pipeline_id}")
        
        jobs = self._get_pipeline_jobs(pipeline_id)
        for job in jobs:
            if job["status"] != "success":
                self._debug_failed_job(job) 