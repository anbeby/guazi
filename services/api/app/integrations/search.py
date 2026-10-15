# -*- coding: utf-8 -*-
"""全文检索适配器：优先 ElasticSearch，不可用时返回 None 由调用方降级为 SQL LIKE。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings


class Search:
    def __init__(self) -> None:
        self._base = settings.ELASTICSEARCH_URL.rstrip("/")
        self._healthy = False
        self.check()

    # ------------------------------------------------------------------ 健康
    def check(self) -> bool:
        if not settings.ELASTICSEARCH_ENABLED:
            self._healthy = False
            return False
        try:
            response = httpx.get(f"{self._base}/_cluster/health", timeout=2)
            self._healthy = response.status_code == 200
        except httpx.HTTPError:
            self._healthy = False
        return self._healthy

    @property
    def engine(self) -> str:
        return "elasticsearch" if self._healthy else "sql"

    def status(self) -> Dict[str, Any]:
        return {"engine": self.engine, "url": self._base, "index": settings.ELASTICSEARCH_INDEX}

    # ------------------------------------------------------------------ 索引
    def ensure_index(self) -> None:
        if not self._healthy:
            return
        try:
            response = httpx.head(f"{self._base}/{settings.ELASTICSEARCH_INDEX}", timeout=3)
            if response.status_code == 404:
                mapping = {
                    "mappings": {
                        "properties": {
                            "id": {"type": "long"},
                            "code": {"type": "keyword"},
                            "name": {"type": "text", "analyzer": "standard"},
                            "category_name": {"type": "keyword"},
                            "enterprise_name": {"type": "keyword"},
                            "spec": {"type": "text"},
                            "grade": {"type": "keyword"},
                            "origin": {"type": "keyword"},
                            "harvest_year": {"type": "keyword"},
                            "status": {"type": "keyword"},
                            "price": {"type": "double"},
                            "available_quantity": {"type": "double"},
                        }
                    }
                }
                httpx.put(
                    f"{self._base}/{settings.ELASTICSEARCH_INDEX}", json=mapping, timeout=5
                )
        except httpx.HTTPError:
            self._healthy = False

    def index_document(self, doc: Dict[str, Any]) -> bool:
        if not self._healthy:
            return False
        doc_id = doc.get("id")
        if doc_id is None:
            return False
        try:
            response = httpx.put(
                f"{self._base}/{settings.ELASTICSEARCH_INDEX}/_doc/{doc_id}",
                json=doc,
                timeout=3,
            )
            return response.status_code < 300
        except httpx.HTTPError:
            self._healthy = False
            return False

    def delete_document(self, doc_id: Any) -> bool:
        if not self._healthy:
            return False
        try:
            response = httpx.delete(
                f"{self._base}/{settings.ELASTICSEARCH_INDEX}/_doc/{doc_id}", timeout=3
            )
            return response.status_code < 300
        except httpx.HTTPError:
            self._healthy = False
            return False

    def search(
        self,
        keyword: str,
        filters: Optional[Dict[str, Any]] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Optional[List[int]]:
        """返回命中的商品 ID 列表；不可用时返回 None（调用方降级）。"""
        if not self._healthy:
            return None
        must: List[Dict[str, Any]] = []
        if keyword:
            must.append(
                {
                    "multi_match": {
                        "query": keyword,
                        "fields": ["name^3", "code^2", "spec", "enterprise_name", "origin"],
                    }
                }
            )
        filter_clauses: List[Dict[str, Any]] = []
        for field, value in (filters or {}).items():
            if value in (None, ""):
                continue
            if isinstance(value, (list, tuple, set)):
                filter_clauses.append({"terms": {field: list(value)}})
            else:
                filter_clauses.append({"term": {field: value}})
        body = {
            "query": {"bool": {"must": must or [{"match_all": {}}], "filter": filter_clauses}},
            "from": max(0, offset),
            "size": max(1, min(limit, 200)),
            "_source": False,
        }
        try:
            response = httpx.post(
                f"{self._base}/{settings.ELASTICSEARCH_INDEX}/_search", json=body, timeout=5
            )
            if response.status_code >= 300:
                return None
            hits = response.json().get("hits", {}).get("hits", [])
            return [int(hit["_id"]) for hit in hits]
        except (httpx.HTTPError, ValueError, KeyError):
            self._healthy = False
            return None


search = Search()
