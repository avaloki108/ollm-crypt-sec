"""Enhanced embedding analysis with UMAP clustering for vulnerability detection."""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

try:
    import umap
    UMAP_AVAILABLE = True
except ImportError:
    UMAP_AVAILABLE = False

try:
    from sklearn.cluster import DBSCAN
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class EmbeddingClustering:
    """UMAP-based clustering for embedding space analysis."""
    
    def __init__(
        self,
        n_components: int = 2,
        n_neighbors: int = 15,
        min_dist: float = 0.1
    ):
        """Initialize embedding clustering.
        
        Args:
            n_components: Number of dimensions for reduction (2 or 3)
            n_neighbors: UMAP n_neighbors parameter
            min_dist: UMAP min_dist parameter
        """
        if not UMAP_AVAILABLE:
            raise ImportError("UMAP is required for embedding clustering. Install with: pip install umap-learn")
        
        self.n_components = n_components
        self.umap_model = umap.UMAP(
            n_components=n_components,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            random_state=42
        )
    
    def reduce_dimensions(
        self,
        embeddings: np.ndarray
    ) -> np.ndarray:
        """Reduce embeddings to lower dimensions using UMAP.
        
        Args:
            embeddings: Numpy array of embeddings (N x 768)
            
        Returns:
            Reduced embeddings (N x n_components)
        """
        if len(embeddings.shape) != 2:
            raise ValueError("Embeddings must be 2D array")
        
        return self.umap_model.fit_transform(embeddings)
    
    def find_clusters(
        self,
        reduced_embeddings: np.ndarray,
        eps: float = 0.5,
        min_samples: int = 2
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Find clusters in reduced embedding space.
        
        Args:
            reduced_embeddings: UMAP-reduced embeddings
            eps: DBSCAN eps parameter
            min_samples: DBSCAN min_samples parameter
            
        Returns:
            Cluster labels and cluster info
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required for clustering")
        
        clustering = DBSCAN(eps=eps, min_samples=min_samples)
        labels = clustering.fit_predict(reduced_embeddings)
        
        # Analyze clusters
        unique_labels = set(labels)
        clusters_info = {
            "n_clusters": len(unique_labels) - (1 if -1 in labels else 0),
            "n_noise": list(labels).count(-1),
            "cluster_sizes": {}
        }
        
        for label in unique_labels:
            if label != -1:
                clusters_info["cluster_sizes"][label] = list(labels).count(label)
        
        return labels, clusters_info
    
    def identify_outliers(
        self,
        embeddings: np.ndarray,
        contract_names: List[str],
        threshold_percentile: float = 95.0
    ) -> List[Dict[str, Any]]:
        """Identify outlier contracts using embedding distances.
        
        Args:
            embeddings: Contract embeddings
            contract_names: Corresponding contract names
            threshold_percentile: Percentile for outlier threshold
            
        Returns:
            List of outlier contracts
        """
        if len(embeddings) < 3:
            return []
        
        # Calculate pairwise distances
        from sklearn.metrics.pairwise import euclidean_distances
        
        distances = euclidean_distances(embeddings)
        
        # Average distance from each contract to all others
        avg_distances = distances.mean(axis=1)
        
        # Threshold based on percentile
        threshold = np.percentile(avg_distances, threshold_percentile)
        
        outliers = []
        for i, (name, avg_dist) in enumerate(zip(contract_names, avg_distances)):
            if avg_dist > threshold:
                outliers.append({
                    "contract": name,
                    "avg_distance": float(avg_dist),
                    "threshold": float(threshold),
                    "is_outlier": True
                })
        
        return sorted(outliers, key=lambda x: x["avg_distance"], reverse=True)
    
    def find_similar_clusters(
        self,
        embeddings: np.ndarray,
        contract_names: List[str],
        vulnerability_embeddings: Dict[str, np.ndarray],
        similarity_threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        """Find contracts that cluster near known vulnerabilities.
        
        Args:
            embeddings: Contract embeddings
            contract_names: Contract names
            vulnerability_embeddings: Dictionary of vulnerability embeddings
            similarity_threshold: Similarity threshold
            
        Returns:
            List of contracts near vulnerability clusters
        """
        from sklearn.metrics.pairwise import cosine_similarity
        
        matches = []
        
        for vuln_name, vuln_emb in vulnerability_embeddings.items():
            similarities = cosine_similarity(
                embeddings,
                vuln_emb.reshape(1, -1)
            ).flatten()
            
            for contract_name, similarity in zip(contract_names, similarities):
                if similarity >= similarity_threshold:
                    matches.append({
                        "contract": contract_name,
                        "vulnerability": vuln_name,
                        "similarity": float(similarity),
                        "cluster_match": True
                    })
        
        return sorted(matches, key=lambda x: x["similarity"], reverse=True)
    
    def analyze_embedding_space(
        self,
        embeddings_dict: Dict[str, np.ndarray],
        vulnerability_embeddings: Optional[Dict[str, np.ndarray]] = None
    ) -> Dict[str, Any]:
        """Comprehensive embedding space analysis.
        
        Args:
            embeddings_dict: Dictionary mapping contract names to embeddings
            vulnerability_embeddings: Optional vulnerability embeddings for matching
            
        Returns:
            Analysis results with clusters, outliers, and matches
        """
        if not embeddings_dict:
            return {"error": "No embeddings provided"}
        
        contract_names = list(embeddings_dict.keys())
        embeddings = np.stack([embeddings_dict[name] for name in contract_names])
        
        # Reduce dimensions
        reduced = self.reduce_dimensions(embeddings)
        
        # Find clusters
        labels, cluster_info = self.find_clusters(reduced)
        
        # Identify outliers
        outliers = self.identify_outliers(embeddings, contract_names)
        
        # Find vulnerability matches
        vuln_matches = []
        if vulnerability_embeddings:
            vuln_matches = self.find_similar_clusters(
                embeddings,
                contract_names,
                vulnerability_embeddings
            )
        
        # Assign contracts to clusters
        contract_clusters = {}
        for name, label in zip(contract_names, labels):
            contract_clusters[name] = int(label)
        
        return {
            "n_contracts": len(contract_names),
            "n_clusters": cluster_info["n_clusters"],
            "n_outliers": len(outliers),
            "outliers": outliers,
            "vulnerability_matches": vuln_matches,
            "contract_clusters": contract_clusters,
            "cluster_info": cluster_info,
            "reduced_dimensions": reduced.tolist()  # For visualization
        }

