"""
Render Agent (The Builder)

Responsible for translating the deterministic TimelineManifest into executable 
FFmpeg commands and actively running them in a subprocess to produce the final 
video artifact.
"""

from typing import Dict, Any, List, Tuple, Optional
import logging
import subprocess
import os
from core.models import TimelineManifest, RenderReceipt
from core.media_intelligence import MediaIntelligenceDB

logger = logging.getLogger(__name__)

class RenderAgent:
    def __init__(self, media_db: MediaIntelligenceDB, constitution=None):
        self.media_db = media_db
        self.constitution = constitution
        self.name = "Render_Agent"
        
    def generate_and_execute(self, manifest: TimelineManifest) -> Optional[RenderReceipt]:
        """
        Translates the manifest into FFmpeg commands and executes them.
        
        Returns:
            Optional[RenderReceipt]: The receipt if successful, None otherwise
        """
        logger.info(f"[{self.name}] Translating TimelineManifest v{manifest.version} into execution instructions.")
        
        if self.constitution and not self.constitution.evaluate_action(self.name, "render", {"manifest": manifest}):
            logger.error(f"[{self.name}] Constitution rejected render action.")
            return None
        
        import uuid
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(".cineflow", "renders", manifest.project_id, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        commands = []
        
        concat_list_path = os.path.join(job_dir, "concat_list.txt")
        primary_track_path = os.path.join(job_dir, "primary_track.mp4")
        final_output_path = os.path.join(job_dir, f"final_output_v{manifest.version}.mp4")
        
        # 1. Base A-Roll Cuts
        clip_paths = []
        for idx, decision in enumerate(manifest.v1_audio_video):
            asset = self.media_db.get_asset(decision.clip_id)
            if not asset or not getattr(asset, 'source_uri', None):
                logger.error(f"[{self.name}] Asset {decision.clip_id} missing. Failing closed.")
                return None
            source_uri = os.path.abspath(asset.source_uri)
            if not os.path.exists(source_uri):
                logger.error(f"[{self.name}] Asset file {source_uri} missing on disk. Failing closed.")
                return None
            
            out_clip = os.path.join(job_dir, f"temp_v{manifest.version}_clip_{idx}.mp4")
            clip_paths.append(out_clip)
            cmd = [
                "ffmpeg", "-i", source_uri, 
                "-ss", f"{decision.start_time:.3f}", 
                "-to", f"{decision.end_time:.3f}", 
                "-c:v", "libx264", "-c:a", "aac", 
                "-avoid_negative_ts", "make_zero", 
                out_clip, "-y"
            ]
            commands.append(cmd)
            
        # 2. Concat A-Rolls
        concat_cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", 
            "-i", concat_list_path, "-c", "copy", 
            primary_track_path, "-y"
        ]
        commands.append(concat_cmd)
        
        # 3. Add B-Rolls (if any)
        current_input = primary_track_path
        if manifest.v2_video_only:
            for b_idx, broll in enumerate(manifest.v2_video_only):
                b_asset = self.media_db.get_asset(broll.clip_id)
                if not b_asset or not getattr(b_asset, 'source_uri', None):
                    logger.error(f"[{self.name}] B-Roll {broll.clip_id} missing. Failing closed.")
                    return None
                broll_uri = os.path.abspath(b_asset.source_uri)
                
                out_layer = os.path.join(job_dir, f"layer_v_{b_idx}.mp4")
                overlay_cmd = [
                    "ffmpeg", "-i", current_input, "-i", broll_uri,
                    "-filter_complex", f"[0:v][1:v]overlay=enable='between(t,{broll.insert_at_timeline:.3f},{broll.insert_at_timeline + broll.duration:.3f})'[outv]",
                    "-map", "[outv]", "-map", "0:a", "-c:a", "copy", 
                    out_layer, "-y"
                ]
                commands.append(overlay_cmd)
                current_input = out_layer

        # 4. Mix Voiceovers/Audio (if any)
        if getattr(manifest, 'a1_audio_only', None):
            for a_idx, a_insert in enumerate(manifest.a1_audio_only):
                # We assume the asset_id is the filename in the working directory or full path
                audio_uri = a_insert.asset_id
                if not os.path.exists(audio_uri):
                     audio_uri = f"{a_insert.asset_id}.mp3" # Fallback if they didn't include extension
                if not os.path.exists(audio_uri):
                    logger.error(f"[{self.name}] Audio file {audio_uri} missing. Failing closed.")
                    return None
                
                out_layer = os.path.join(job_dir, f"layer_a_{a_idx}.mp4")
                # Use amix to mix original audio and voiceover delayed by insert_at_timeline
                delay_ms = int(a_insert.insert_at_timeline * 1000)
                mix_cmd = [
                    "ffmpeg", "-i", current_input, "-i", audio_uri,
                    "-filter_complex", f"[1:a]adelay={delay_ms}|{delay_ms}[delayed]; [0:a][delayed]amix=inputs=2:duration=first[outa]",
                    "-map", "0:v", "-map", "[outa]", "-c:v", "copy", 
                    out_layer, "-y"
                ]
                commands.append(mix_cmd)
                current_input = out_layer
        
        # 5. Final Output rename
        commands.append(["python", "-c", f"import os, shutil; shutil.copy(r'{current_input}', r'{final_output_path}')"])

        # 4. EXECUTE COMMANDS
        logger.info(f"[{self.name}] Writing {concat_list_path}...")
        with open(concat_list_path, "w") as f:
            for clip_path in clip_paths:
                f.write(f"file '{os.path.abspath(clip_path).replace(chr(92), '/')}'\n")
                
        logger.info(f"[{self.name}] Executing {len(commands)} FFmpeg commands via subprocess...")
        print(f"[{self.name}] Starting render pipeline with {len(commands)} steps. This may take a moment...")
        for i, cmd in enumerate(commands, 1):
            try:
                cmd_str = " ".join(cmd)
                print(f"[{self.name}] Progress: Rendering step {i} of {len(commands)}...")
                logger.info(f"Running: {cmd_str}")
                subprocess.run(cmd, shell=False, capture_output=True, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"[{self.name}] FFmpeg failed: {e.stderr}")
                return None
            except Exception as e:
                logger.error(f"[{self.name}] Subprocess crashed: {str(e)}")
                return None
                
        import hashlib
        import hmac
        
        output_file = final_output_path
        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            logger.error(f"[{self.name}] Output artifact missing or empty. Render failed.")
            return None
            
        # Final FFprobe validation
        try:
            probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", output_file]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            duration = float(probe_result.stdout.strip())
            if duration <= 0:
                logger.error(f"[{self.name}] Output artifact has invalid duration {duration}. Render failed.")
                return None
        except Exception as e:
            logger.error(f"[{self.name}] Final FFprobe validation failed: {str(e)}")
            return None
            
        # Get hash
        with open(output_file, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        manifest_json = manifest.model_dump_json().encode('utf-8')
        manifest_hash = hashlib.sha256(manifest_json).hexdigest()
        
        # Unforgeable signature
        secret_key = os.environ.get("CINEFLOW_SIGNING_SECRET")
        if not secret_key:
            logger.error(f"[{self.name}] CINEFLOW_SIGNING_SECRET not configured. Cannot sign receipt.")
            return None
        signature_payload = f"{manifest_hash}:{file_hash}".encode('utf-8')
        executor_signature = hmac.new(secret_key.encode('utf-8'), signature_payload, hashlib.sha256).hexdigest()
            
        from core.models import RenderReceipt
        receipt = RenderReceipt(
            project_id=manifest.project_id,
            manifest_version=manifest.version,
            manifest_hash=manifest_hash,
            artifact_path=output_file,
            artifact_sha256=file_hash,
            render_job_id=job_id,
            ffmpeg_exit_code=0,
            executor_signature=executor_signature
        )
                
        logger.info(f"[{self.name}] Render execution completed successfully.")
        return receipt
