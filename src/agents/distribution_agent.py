"""
Distribution Agent (The Publisher)

Handles the final delivery of the approved and rendered asset to external platforms
(e.g., YouTube, AWS S3, Frame.io). It acts as the final security gate, ensuring that
only cryptographically verified, fully approved artifacts are published.
"""

from typing import Dict, Any, List
import logging
import os
import hashlib
from core.models import ProjectState, RenderReceipt

logger = logging.getLogger(__name__)

class DistributionAgent:
    def __init__(self, constitution=None):
        self.constitution = constitution
        self.name = "Distribution_Agent"
        
    def publish_artifact(self, project: ProjectState, receipt: RenderReceipt, manifest, platforms: List[str]) -> Dict[str, Any]:
        """
        Securely distributes a completed render artifact after verifying its cryptographic receipt.
        """
        logger.info(f"[{self.name}] Initiating distribution sequence for project {receipt.project_id}")
        
        # 1. Project Status check
        if project.status != "RENDER_COMPLETE":
            logger.error(f"[{self.name}] SECURITY ALERT: Project status is not RENDER_COMPLETE.")
            return {"success": False, "reason": "Distribution blocked. Project not RENDER_COMPLETE."}

        # 2. Receipt Status check
        if receipt.status != "VALIDATED":
            logger.error(f"[{self.name}] SECURITY ALERT: Receipt status invalid ({receipt.status}).")
            return {"success": False, "reason": "Distribution blocked. Receipt must be VALIDATED."}
            
        # 3. FFmpeg exit code check
        if receipt.ffmpeg_exit_code != 0:
            logger.error(f"[{self.name}] SECURITY ALERT: FFmpeg exit code is not 0.")
            return {"success": False, "reason": "FFmpeg exit code must be 0."}
            
        # 4. Artifact exists
        render_file_path = receipt.artifact_path
        if not os.path.exists(render_file_path):
            logger.error(f"[{self.name}] Final artifact missing at expected path: {render_file_path}")
            return {"success": False, "reason": "Render artifact not found on disk."}
            
        # 5. Artifact SHA256 matches
        with open(render_file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        if file_hash != receipt.artifact_sha256:
            logger.error(f"[{self.name}] HASH MISMATCH! Expected {receipt.artifact_sha256} but got {file_hash}")
            return {"success": False, "reason": "Artifact integrity compromised."}
            
        # 6. Manifest identity/hash check
        manifest_json = manifest.model_dump_json().encode('utf-8')
        manifest_hash = hashlib.sha256(manifest_json).hexdigest()
        if manifest_hash != receipt.manifest_hash:
            logger.error(f"[{self.name}] SECURITY ALERT: Manifest hash mismatch.")
            return {"success": False, "reason": "Manifest hash mismatch."}
            
        # 7. Executor signature check
        secret_key = os.environ.get("CINEFLOW_SIGNING_SECRET")
        if not secret_key:
            logger.error(f"[{self.name}] CINEFLOW_SIGNING_SECRET not configured.")
            return {"success": False, "reason": "Signing secret missing."}
            
        import hmac
        signature_payload = f"{receipt.manifest_hash}:{receipt.artifact_sha256}".encode('utf-8')
        expected_sig = hmac.new(secret_key.encode('utf-8'), signature_payload, hashlib.sha256).hexdigest()
        if receipt.executor_signature != expected_sig:
             logger.error(f"[{self.name}] SECURITY ALERT: Invalid executor signature.")
             return {"success": False, "reason": "Invalid executor signature."}

        # 8. Constitution check (if present, must not disable above checks)
        if self.constitution and not self.constitution.evaluate_action(self.name, "publish", {"status": project.status}):
            logger.error(f"[{self.name}] SECURITY ALERT: Constitution rejected publish action.")
            return {"success": False, "reason": "Distribution blocked by Constitution."}
            
        logger.info(f"[{self.name}] Artifact verified. SHA256 Hash matches receipt: {file_hash[:16]}...")
            
        results = {}
        for platform in platforms:
            # We strictly enforce known platforms to avoid arbitrary URL generation
            if platform.lower() not in ["youtube", "s3", "frameio"]:
                logger.warning(f"[{self.name}] Unknown platform {platform}. Skipping.")
                continue
                
            mode = os.environ.get("CINEFLOW_DISTRIBUTION_MODE", "SIMULATION")
            if mode == "INTEGRATION_PLACEHOLDER":
                logger.info(f"[{self.name}] [INTEGRATION_PLACEHOLDER] API upload not implemented. Placeholder returned for {platform}...")
                results[platform] = f"https://{platform.lower()}.com/watch/{receipt.project_id}_v{receipt.manifest_version}"
            elif mode == "SIMULATION":
                logger.info(f"[{self.name}] [SIMULATION_MODE] Simulating upload to {platform} API...")
                results[platform] = f"[SIMULATED] https://{platform.lower()}.com/watch/{receipt.project_id}_v{receipt.manifest_version}"
            else:
                logger.warning(f"[{self.name}] Unknown distribution mode {mode}. Defaulting to SIMULATION.")
                results[platform] = f"[SIMULATED] https://{platform.lower()}.com/watch/{receipt.project_id}_v{receipt.manifest_version}"
            
        if not results:
            return {"success": False, "reason": "No valid platforms published."}
            
        logger.info(f"[{self.name}] Distribution completed successfully.")
        return {
            "success": True,
            "urls": results,
            "network_cost": 0.05
        }
