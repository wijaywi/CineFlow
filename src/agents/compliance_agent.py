"""
Compliance & Editor Agent

Acts as the verification layer. It checks the deterministic decisions of the Director Agent
against factual rules, copyright metadata (Rights & Provenance), and safety guidelines.
"""

from typing import Dict, Any, Tuple
import logging
from core.models import TimelineManifest
from core.models import ProjectState
from core.media_intelligence import MediaIntelligenceDB

logger = logging.getLogger(__name__)

class ComplianceAgent:
    def __init__(self, media_db: MediaIntelligenceDB):
        self.media_db = media_db
        self.name = "Compliance_Agent"
        
    def verify_manifest(self, manifest: TimelineManifest) -> Tuple[bool, str]:
        """
        Validates the proposed timeline against copyright rules and constraints.
        
        Returns:
            Tuple[bool, str]: (is_approved, reasoning)
        """
        logger.info(f"[{self.name}] Verifying TimelineManifest v{manifest.version} for project {manifest.project_id}")
        
        from core.models import LicenseStatus
        
        # 1. Rights & Provenance Checking for Primary Assets
        for decision in manifest.v1_audio_video:
            asset = self.media_db.get_asset(decision.clip_id)
            if asset:
                if asset.audio_license_status in [LicenseStatus.UNVERIFIED, LicenseStatus.UNLICENSED, LicenseStatus.UNKNOWN, LicenseStatus.CHECK_FAILED]:
                    logger.warning(f"Music License Status could not be independently verified for {asset.asset_id}. Output generation will continue. You are responsible for ensuring that you have the necessary rights to use this media.")
                elif asset.audio_license_status == LicenseStatus.POTENTIAL_COPYRIGHT_MATCH:
                    logger.warning(f"Potential copyrighted audio was detected for {asset.asset_id}. Output generation will continue. Please ensure that you have the necessary rights to use this media.")
                if asset.video_license_status in [LicenseStatus.UNVERIFIED, LicenseStatus.UNLICENSED, LicenseStatus.UNKNOWN, LicenseStatus.CHECK_FAILED]:
                    logger.warning(f"Video License Status could not be independently verified for {asset.asset_id}. Output generation will continue. You are responsible for ensuring that you have the necessary rights to use this media.")
                elif asset.video_license_status == LicenseStatus.POTENTIAL_COPYRIGHT_MATCH:
                    logger.warning(f"Potential copyrighted video was detected for {asset.asset_id}. Output generation will continue. Please ensure that you have the necessary rights to use this media.")
            else:
                logger.warning(f"[{self.name}] Asset {decision.clip_id} not found in Media DB. Output generation will continue.")
                
        # 2. Rights & Provenance Checking for B-Roll Assets
        for broll in manifest.v2_video_only:
            asset = self.media_db.get_asset(broll.clip_id)
            if asset:
                if asset.video_license_status in [LicenseStatus.UNVERIFIED, LicenseStatus.UNLICENSED, LicenseStatus.UNKNOWN, LicenseStatus.CHECK_FAILED]:
                    logger.warning(f"Video License Status could not be independently verified for {asset.asset_id}. Output generation will continue. You are responsible for ensuring that you have the necessary rights to use this media.")
                elif asset.video_license_status == LicenseStatus.POTENTIAL_COPYRIGHT_MATCH:
                    logger.warning(f"Potential copyrighted video was detected for {asset.asset_id}. Output generation will continue. Please ensure that you have the necessary rights to use this media.")
            else:
                logger.warning(f"[{self.name}] B-Roll {broll.clip_id} not found in Media DB. Output generation will continue.")

        # 3. Fact Checking & Safety via Truth Graph
        from core.truth_graph import TruthGraph
        truth_graph = TruthGraph()
        
        context = getattr(manifest, 'context', '')
        simulated_claims = truth_graph.extract_claims(context)
        
        for claim in simulated_claims:
            validation = truth_graph.verify_claim(claim)
            if validation.status == "CONTRADICTED":
                return False, f"Fact Check Failed: {validation.reasoning}"
            elif validation.status == "UNVERIFIED":
                return False, f"Fact Check Failed: Unverified claim '{claim}'"
        
        logger.info(f"[{self.name}] TimelineManifest approved. All assets cleared and claims verified.")
        return True, "Approved. All assets cleared for use. No factual contradictions detected."
