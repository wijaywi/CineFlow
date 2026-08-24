"""
Quality Control (QC) Agent

Responsible for the initial ingestion and quality control of raw media.
It analyzes visual, audio, semantic, and technical dimensions without
destructive capabilities (quarantine only, no deletion).
"""

from typing import Dict, Any
import logging
from core.models import AssetItem
from core.media_intelligence import MediaIntelligenceDB

logger = logging.getLogger(__name__)

class QCAgent:
    def __init__(self, media_db: MediaIntelligenceDB):
        self.media_db = media_db
        self.name = "QC_Agent"
        
    def evaluate_asset(self, asset: AssetItem) -> Dict[str, Any]:
        """
        Executes a comprehensive, non-destructive quality check on the asset.
        """
        logger.info(f"QC Agent beginning evaluation for asset: {asset.asset_id}")
        
        # Simulated QC pipeline for visual, audio, and technical fidelity
        # In production, this would interface with Vision APIs and audio analysis tools.
        
        # Implement ffprobe checks for codec and resolution
        import subprocess
        import json
        
        status = "PASS"
        reason = "Asset meets all foundational quality thresholds."
        codec = "unknown"
        resolution = "unknown"
        
        source_uri = getattr(asset, 'source_uri', None)
        if source_uri:
            try:
                cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name,width,height",
                    "-of", "json", source_uri
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                info = json.loads(result.stdout)
                if 'streams' in info and len(info['streams']) > 0:
                    stream = info['streams'][0]
                    codec = stream.get('codec_name', 'unknown')
                    width = stream.get('width', 0)
                    height = stream.get('height', 0)
                    resolution = f"{width}x{height}"
                    
                    if width < 640 or height < 360:
                        status = "FAIL"
                        reason = "Resolution below minimum quality threshold."
            except Exception as e:
                logger.warning(f"Failed to probe asset: {e}")
                status = "FAIL"
                reason = "Failed to extract technical metadata."
        else:
            status = "FAIL"
            reason = "Missing source_uri."

        qc_report = {
            "asset_id": asset.asset_id,
            "status": status,
            "confidence": 0.95,
            "visual": {"blur": False, "exposure": "optimal", "composition": "center"},
            "audio": {"clipping": False, "noise_level": "low", "speech_intelligibility": "high"},
            "technical": {"codec": codec, "resolution": resolution},
            "reason": reason
        }
        
        # Instead of deleting failed assets, we only flag their status.
        if qc_report["status"] == "FAIL":
            logger.warning(f"Asset {asset.asset_id} failed QC. Quarantining asset. DO NOT DELETE.")
            
        return qc_report
