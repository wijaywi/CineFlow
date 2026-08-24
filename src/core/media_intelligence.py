"""
Media Intelligence Database

This module serves as the 'Visual Brain' of the CineFlow AI pipeline.
It handles indexing, auto-tagging, and semantic vector search for B-Roll 
and primary assets, preventing the need for agents to repeatedly process raw video.
"""

from typing import List, Dict, Any, Optional
from .models import AssetItem
import logging

logger = logging.getLogger(__name__)

class MediaIntelligenceDB:
    def __init__(self):
        # In a production environment, this integrates with vector databases 
        # such as ChromaDB, Milvus, or Qdrant for high-speed semantic search.
        self._asset_store: Dict[str, AssetItem] = {}
        self._vector_store: Dict[str, Any] = {}
        
    def _get_embedding(self, text: str) -> List[float]:
        import os
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return []
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            return result.embeddings[0].values
        except ImportError:
            logger.warning("google.genai package not installed. Embedding unavailable.")
            return []
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
            return []

    def ingest_asset(self, asset: AssetItem) -> None:
        """
        Stores the immutable asset record and its extracted metadata.
        Generates semantic embeddings using Google GenAI if not present.
        """
        if asset.asset_id in self._asset_store:
            raise ValueError(f"CRITICAL: Asset {asset.asset_id} already exists. Immutability violation.")
        
        # Generate embedding for the asset description/tags
        text_to_embed = asset.metadata.get('description', '') + " " + " ".join(asset.metadata.get('tags', []))
        if not text_to_embed.strip():
            text_to_embed = asset.asset_type + " " + asset.asset_id
            
        logger.info(f"Generating embedding for asset {asset.asset_id}...")
        embedding = self._get_embedding(text_to_embed)
        if embedding:
            self._vector_store[asset.asset_id] = embedding
            
        self._asset_store[asset.asset_id] = asset
        logger.info(f"Asset {asset.asset_id} successfully ingested into Media Intelligence Database.")
        
    def search_broll(self, query: str, min_duration: float = 0.0) -> List[AssetItem]:
        """
        Performs a semantic search against the vector database for B-Roll assets
        using Cosine Similarity on Google GenAI Text Embeddings.
        Fallbacks to keyword search if embedding is not available.
        """
        logger.info(f"Performing search for B-Roll: '{query}'")
        
        query_embedding = self._get_embedding(query)
        candidates = [a for a in self._asset_store.values() if a.asset_type == "B-Roll"]
        
        matched_assets = []
        if query_embedding:
            logger.info("Using real semantic vector search.")
            import math
            def cosine_similarity(v1, v2):
                if not v1 or not v2: return 0.0
                dot = sum(x*y for x, y in zip(v1, v2))
                mag1 = math.sqrt(sum(x*x for x in v1))
                mag2 = math.sqrt(sum(y*y for y in v2))
                if mag1 * mag2 == 0: return 0.0
                return dot / (mag1 * mag2)
                
            results = []
            for asset in candidates:
                asset_embedding = self._vector_store.get(asset.asset_id)
                if asset_embedding:
                    similarity = cosine_similarity(query_embedding, asset_embedding)
                    logger.info(f"Similarity for {asset.asset_id}: {similarity:.4f}")
                    if similarity > 0.60:
                        results.append((similarity, asset))
            
            results.sort(key=lambda x: x[0], reverse=True)
            matched_assets = [r[1] for r in results]
        else:
            logger.warning("No query embedding generated. Falling back to keyword search.")
            query_lower = query.lower()
            for asset in candidates:
                text_to_search = (asset.metadata.get('description', '') + " " + " ".join(asset.metadata.get('tags', []))).lower()
                query_words = set(query_lower.split())
                search_words = set(text_to_search.split())
                if query_words.intersection(search_words) or query_lower in text_to_search:
                    matched_assets.append(asset)
                    
        final_results = []
        for asset in matched_assets:
            duration = asset.metadata.get('duration', float('inf'))
            if duration >= min_duration:
                final_results.append(asset)
                
        return final_results
        
    def get_asset(self, asset_id: str) -> Optional[AssetItem]:
        """Retrieves an immutable asset record by ID."""
        return self._asset_store.get(asset_id)
