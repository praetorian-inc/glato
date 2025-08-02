"""
End-to-end tests for GitLab self-hosted Runner functionality.

This module tests runner functionality specifically on self-hosted GitLab,
focusing on self-hosted-specific runner configurations and behaviors.
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


class TestSelfHostedRunners:
    """GitLab Runner tests specifically for self-hosted environments."""
    
    @pytest.fixture(autouse=True)
    def setup(self, gitlab_url, tokens):
        """Set up test environment for self-hosted testing."""
        self.gitlab_url = gitlab_url
        
        # Self-hosted token configuration
        self.token = (
            tokens.get('SELF_HOSTED_ADMIN_TOKEN') or
            tokens.get('SELF_HOSTED_ALICE_TOKEN') or 
            os.getenv("SELF_HOSTED_ADMIN_TOKEN") or
            os.getenv("SELF_HOSTED_ALICE_TOKEN") or
            # Legacy fallback
            os.getenv("TF_VAR_gitlab_token") or
            tokens.get('GITLAB_TOKEN') or 
            os.getenv("GITLAB_TOKEN")
        )
        assert self.token, ("Self-hosted token required. Set SELF_HOSTED_ADMIN_TOKEN or "
                           "SELF_HOSTED_ALICE_TOKEN for self-hosted testing")
        
        # Self-hosted project configuration  
        self.project_path = "acme-corporation-glato/product-glato/api-glato/api-service-glato"
        
        # Get project and group IDs dynamically
        self._get_selfhosted_ids()
        
        # Set up headers for self-hosted
        self.headers = {"PRIVATE-TOKEN": self.token, "Content-Type": "application/json"}
        
        # Generate unique test ID for isolation
        self.test_id = str(uuid.uuid4())[:8]
        
        print(f"🔧 Setup complete for self-hosted project {self.project_id} (test ID: {self.test_id})")

    def _get_selfhosted_ids(self):
        """Get project and group IDs for self-hosted environment."""
        # Get project ID
        response = requests.get(
            f"{self.gitlab_url}/api/v4/projects/{self.project_path.replace('/', '%2F')}",
            headers={"PRIVATE-TOKEN": self.token},
            verify=False
        )
        assert response.status_code == 200, f"Failed to get project info: {response.status_code} - {response.text}"
        project_info = response.json()
        self.project_id = str(project_info["id"])
        
        # Get product group ID
        response = requests.get(
            f"{self.gitlab_url}/api/v4/groups/acme-corporation-glato%2Fproduct-glato",
            headers={"PRIVATE-TOKEN": self.token},
            verify=False
        )
        assert response.status_code == 200, f"Failed to get product group info: {response.status_code}"
        group_info = response.json()
        self.group_id = str(group_info["id"])

    def test_runners_are_online(self):
        """Test that required runners are online and properly configured on self-hosted."""
        print("🔍 Testing self-hosted runner availability...")
        
        # Check project runners
        response = requests.get(
            f"{self.gitlab_url}/api/v4/projects/{self.project_id}/runners",
            headers=self.headers,
            verify=False
        )
        assert response.status_code == 200, f"Failed to get project runners: {response.status_code}"
        
        project_runners = response.json()
        
        # Self-hosted runners - check project, group, and instance runners
        online_project_runners = [r for r in project_runners if r.get("status") == "online"]
        assert len(online_project_runners) >= 1, "At least 1 project runner should be online on self-hosted"
        
        # Check group runners
        response = requests.get(
            f"{self.gitlab_url}/api/v4/groups/{self.group_id}/runners",
            headers=self.headers,
            verify=False
        )
        if response.status_code == 200:
            group_runners = response.json()
            online_group_runners = [r for r in group_runners if r.get("status") == "online"]
            print(f"✅ Self-hosted group runners online: {len(online_group_runners)}")
        
        # Check instance runners (requires admin)
        response = requests.get(
            f"{self.gitlab_url}/api/v4/runners/all",
            headers=self.headers,
            verify=False
        )
        if response.status_code == 403:
            print("⚠️  Admin privileges required to check instance runners")
        
        print(f"✅ Self-hosted project runners online: {len(online_project_runners)}")

    def test_project_runner_execution(self):
        """Test project runner job execution on self-hosted."""
        print("🚀 Testing self-hosted project runner job execution...")
        
        # Wait to avoid conflicts from previous tests
        time.sleep(5)
        
        config = f"""stages:
  - test

project_runner_test_{self.test_id}:
  stage: test
  image: ubuntu:22.04
  script:
    - echo Project runner test {self.test_id}
    - echo Environment Self-hosted
    - echo Timestamp $(date)
    - sleep 2
    - echo Project runner test complete
"""
        
        pipeline_id = self._create_and_wait_for_pipeline(
            config, 
            f"Test self-hosted project runner {self.test_id}",
            timeout=120
        )
        
        jobs = self._get_pipeline_jobs(pipeline_id)
        assert len(jobs) == 1, f"Expected 1 job, got {len(jobs)}"
        
        job = jobs[0]
        
        if job['status'] != 'success':
            print(f"❌ Job failed. Details: {job}")
            self._debug_failed_job(job)
        
        assert job["status"] == "success", f"Job should succeed, got: {job['status']}"
        
        print("✅ Self-hosted project runner execution successful")

    def test_group_runner_execution(self):
        """Test group runner job execution on self-hosted."""
        print("🚀 Testing self-hosted group runner job execution...")
        
        # Wait to avoid conflicts
        time.sleep(5)
        
        config = f"""stages:
  - test

group_runner_test_{self.test_id}:
  stage: test
  image: ubuntu:22.04
  script:
    - echo Group runner test {self.test_id}
    - echo Environment Self-hosted
    - echo Timestamp $(date)
    - sleep 2
    - echo Group runner test complete
"""
        
        pipeline_id = self._create_and_wait_for_pipeline(
            config, 
            f"Test self-hosted group runner {self.test_id}",
            timeout=120
        )
        
        jobs = self._get_pipeline_jobs(pipeline_id)
        assert len(jobs) == 1, f"Expected 1 job, got {len(jobs)}"
        
        job = jobs[0]
        
        if job['status'] != 'success':
            print(f"❌ Job failed. Details: {job}")
            self._debug_failed_job(job)
        
        assert job["status"] == "success", f"Job should succeed, got: {job['status']}"
        
        print("✅ Self-hosted group runner execution successful")

    def test_parallel_runner_execution(self):
        """Test parallel runner job execution on self-hosted."""
        print("🚀 Testing self-hosted parallel runner execution...")
        
        # Wait to avoid conflicts
        time.sleep(10)
        
        config = f"""
stages:
  - test

parallel_test_{self.test_id}:
  stage: test
  image: ubuntu:22.04
  script:
    - echo Parallel test {self.test_id}
    - echo Environment Self-hosted
    - echo Job """ + "${CI_JOB_NAME}" + f"""
    - sleep 3
    - echo Parallel test complete
  parallel: 2
"""
        
        pipeline_id = self._create_and_wait_for_pipeline(
            config, 
            f"Test self-hosted parallel runners {self.test_id}",
            timeout=180
        )
        
        jobs = self._get_pipeline_jobs(pipeline_id)
        assert len(jobs) == 2, f"Expected 2 jobs, got {len(jobs)}"
        
        # Verify all jobs succeeded
        for job in jobs:
            if job['status'] != 'success':
                print(f"❌ Job {job['name']} failed. Details: {job}")
                self._debug_failed_job(job)
            assert job["status"] == "success", f"Job {job['name']} should succeed, got: {job['status']}"
        
        print("✅ Self-hosted parallel runner execution successful")

    def test_instance_runner_availability(self):
        """Test instance runner availability on self-hosted (if admin access available)."""
        print("🔍 Testing self-hosted instance runner availability...")
        
        response = requests.get(
            f"{self.gitlab_url}/api/v4/runners/all",
            headers=self.headers,
            verify=False
        )
        
        if response.status_code == 403:
            print("⚠️  Admin privileges required to check instance runners - skipping")
            pytest.skip("Admin privileges required for instance runner checks")
        
        assert response.status_code == 200, f"Failed to get instance runners: {response.status_code}"
        
        runners = response.json()
        online_runners = [r for r in runners if r.get("status") == "online"]
        
        print(f"✅ Found {len(online_runners)} online instance runners on self-hosted")
        
        # At least some runners should be available
        assert len(runners) > 0, "No instance runners found on self-hosted"

    def _create_and_wait_for_pipeline(self, config: str, commit_message: str, timeout: int = 120) -> int:
        """Create a pipeline and wait for completion on self-hosted."""
        print(f"📝 Creating pipeline: {commit_message}")
        
        # Create temporary directory for git operations
        temp_dir = Path("/tmp") / f"glato_test_{self.test_id}"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Clone the repository
            clone_url = f"{self.gitlab_url}/{self.project_path}.git"
            # Add token to URL for authentication
            auth_url = clone_url.replace("://", f"://oauth2:{self.token}@")
            repo = Repo.clone_from(auth_url, temp_dir)
            
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
                params={"ref": branch_name, "per_page": 1},
                verify=False
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
                    headers=self.headers,
                    verify=False
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
        """Get jobs for a pipeline on self-hosted."""
        response = requests.get(
            f"{self.gitlab_url}/api/v4/projects/{self.project_id}/pipelines/{pipeline_id}/jobs",
            headers=self.headers,
            verify=False
        )
        assert response.status_code == 200, f"Failed to get pipeline jobs: {response.status_code}"
        return response.json()

    def _debug_failed_job(self, job):
        """Debug a failed job on self-hosted."""
        print(f"🔍 Debugging failed job {job['id']}: {job['name']}")
        
        # Get job trace
        response = requests.get(
            f"{self.gitlab_url}/api/v4/projects/{self.project_id}/jobs/{job['id']}/trace",
            headers=self.headers,
            verify=False
        )
        if response.status_code == 200:
            print(f"📋 Job trace:\n{response.text}")
        else:
            print(f"❌ Could not get job trace: {response.status_code}")

    def _debug_failed_pipeline(self, pipeline_id):
        """Debug a failed pipeline on self-hosted."""
        print(f"🔍 Debugging failed pipeline {pipeline_id}")
        
        jobs = self._get_pipeline_jobs(pipeline_id)
        for job in jobs:
            if job["status"] != "success":
                self._debug_failed_job(job) 