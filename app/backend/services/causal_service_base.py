"""
因果服务基类 - Causal Service Base

提供所有因果服务的公共基础设施：
- LLM调用重试和降级机制
- 结果缓存（Redis/内存）
- 错误处理和日志标准化
- 批量异步处理支持
"""

import json
import logging
import time
import hashlib
from typing import Any, Dict, Optional, Callable, List
from functools import wraps
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from services.aihub import AIHubService
from schemas.aihub import GenTxtRequest, ChatMessage

logger = logging.getLogger(__name__)


# 简单的内存缓存实现（生产环境建议替换为Redis）
class InMemoryCache:
    """内存缓存 - 用于缓存因果分析结果"""

    def __init__(self, ttl_seconds: int = 3600):  # 默认1小时TTL
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self._cache:
            self._misses += 1
            return None

        value, expire_time = self._cache[key]
        if time.time() > expire_time:
            del self._cache[key]
            self._misses += 1
            return None

        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """设置缓存"""
        ttl = ttl_seconds or self._ttl
        expire_time = time.time() + ttl
        self._cache[key] = (value, expire_time)

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate * 100, 1),
            "size": len(self._cache)
        }

    def cleanup(self) -> int:
        """清理过期项"""
        now = time.time()
        expired_keys = [
            k for k, (v, et) in self._cache.items()
            if now > et
        ]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)


# 全局缓存实例
_cache = InMemoryCache()


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """生成缓存键"""
    content = f"{prefix}:{str(args)}:{str(sorted(kwargs.items()))}"
    return hashlib.md5(content.encode()).hexdigest()


def with_cache(ttl_seconds: int = 3600):
    """缓存装饰器"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = generate_cache_key(func.__name__, *args, **kwargs)

            # 尝试获取缓存
            cached = _cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached

            # 未命中，执行函数
            result = await func(*args, **kwargs)

            # 缓存结果
            _cache.set(cache_key, result, ttl_seconds)

            return result

        return wrapper

    return decorator


def with_retry(max_retries: int = 3, backoff_factor: float = 1.0):
    """重试装饰器 - 用于LLM调用"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    wait_time = backoff_factor * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} for {func.__name__} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)

            # 所有重试都失败了
            logger.error(f"All {max_retries} attempts failed for {func.__name__}")
            raise last_exception

        return wrapper

    return decorator


class CausalServiceBase:
    """因果服务基类 - 提供公共基础设施"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_service = AIHubService()

    async def safe_llm_call(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "AI_DEFAULT_MODEL",
        temperature: float = 0.1,
        max_tokens: int = 3000,
        fallback_result: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        安全的LLM调用，包含重试、错误处理、降级逻辑

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            fallback_result: 失败时的降级返回结果

        Returns:
            解析后的JSON结果
        """
        try:
            result = await self._llm_call_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return result
        except Exception as e:
            logger.error(f"LLM call failed after all retries: {e}")

            # 返回降级结果
            if fallback_result is not None:
                return fallback_result

            # 默认降级结果
            return {
                "error": "LLM调用失败，返回默认结果",
                "fallback": True,
                "success": False
            }

    @with_retry(max_retries=3, backoff_factor=1.0)
    async def _llm_call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """带重试的LLM调用"""
        request = GenTxtRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt)
            ],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        response = await self.ai_service.gentxt(request)
        return json.loads(response.content)

    def parse_json_safely(
        self,
        text: str,
        fallback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """安全的JSON解析，失败时返回降级结果"""
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败，尝试提取JSON块: {e}")

            # 尝试提取 ```json ... ``` 块
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except:
                    pass

            # 尝试提取第一个 { 到最后一个 }
            brace_start = text.find('{')
            brace_end = text.rfind('}')
            if brace_start >= 0 and brace_end > brace_start:
                try:
                    return json.loads(text[brace_start:brace_end + 1])
                except:
                    pass

            logger.error(f"JSON解析彻底失败，文本前200字符: {text[:200]}")

            if fallback is not None:
                return fallback

            return {
                "parse_error": True,
                "error": "无法解析JSON响应",
                "raw_text": text[:500] if len(text) > 500 else text
            }

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return _cache.stats()

    def clear_cache(self) -> None:
        """清空缓存（用于测试或强制刷新）"""
        _cache._cache.clear()
        logger.info("Cache cleared")


# 批处理任务状态枚举
class BatchStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial_success"


class BatchProcessor:
    """批量因果分析处理器"""

    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}

    async def submit_batch(
        self,
        task_type: str,
        items: List[Dict[str, Any]],
        processor_func: Callable,
        user_id: Optional[str] = None,
    ) -> str:
        """
        提交批量任务

        Args:
            task_type: 任务类型标识
            items: 待处理项目列表
            processor_func: 处理单个项目的异步函数
            user_id: 关联用户ID

        Returns:
            batch_id 批次ID
        """
        import uuid
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"

        self._tasks[batch_id] = {
            "batch_id": batch_id,
            "task_type": task_type,
            "user_id": user_id,
            "total_items": len(items),
            "completed_items": 0,
            "failed_items": 0,
            "status": BatchStatus.PENDING,
            "results": [],
            "errors": [],
            "created_at": datetime.now().isoformat(),
            "completed_at": None
        }

        # 在后台启动处理（注意：生产环境应该用任务队列如Celery）
        import asyncio
        asyncio.create_task(self._process_batch(batch_id, items, processor_func))

        logger.info(f"Batch {batch_id} submitted: {len(items)} items")
        return batch_id

    async def _process_batch(
        self,
        batch_id: str,
        items: List[Dict[str, Any]],
        processor_func: Callable,
    ):
        """后台处理批量任务"""
        task = self._tasks[batch_id]
        task["status"] = BatchStatus.RUNNING

        results = []
        errors = []

        for i, item in enumerate(items):
            try:
                result = await processor_func(item)
                results.append({
                    "index": i,
                    "success": True,
                    "result": result
                })
                task["completed_items"] += 1
            except Exception as e:
                errors.append({
                    "index": i,
                    "error": str(e),
                    "item": item
                })
                task["failed_items"] += 1
                logger.warning(f"Batch {batch_id} item {i} failed: {e}")

        task["results"] = results
        task["errors"] = errors
        task["completed_at"] = datetime.now().isoformat()

        # 判断最终状态
        if task["failed_items"] == 0:
            task["status"] = BatchStatus.COMPLETED
        elif task["completed_items"] > 0:
            task["status"] = BatchStatus.PARTIAL
        else:
            task["status"] = BatchStatus.FAILED

        logger.info(
            f"Batch {batch_id} completed: {task['completed_items']} success, "
            f"{task['failed_items']} failed, status={task['status']}"
        )

    def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批量任务状态"""
        task = self._tasks.get(batch_id)
        if not task:
            return None

        # 计算进度
        progress = (task["completed_items"] + task["failed_items"]) / task["total_items"] * 100

        return {
            "batch_id": batch_id,
            "task_type": task["task_type"],
            "status": task["status"],
            "total_items": task["total_items"],
            "completed_items": task["completed_items"],
            "failed_items": task["failed_items"],
            "progress_percent": round(progress, 1),
            "created_at": task["created_at"],
            "completed_at": task["completed_at"],
            "has_results": task["status"] in [BatchStatus.COMPLETED, BatchStatus.PARTIAL]
        }

    def get_batch_results(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """获取批量任务结果"""
        task = self._tasks.get(batch_id)
        if not task:
            return None

        return {
            "batch_id": batch_id,
            "status": task["status"],
            "results": task["results"],
            "errors": task["errors"],
            "summary": {
                "total": task["total_items"],
                "success": task["completed_items"],
                "failed": task["failed_items"],
                "success_rate": round(task["completed_items"] / task["total_items"] * 100, 1)
            }
        }

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """清理旧任务"""
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        to_delete = [
            batch_id for batch_id, task in self._tasks.items()
            if task["completed_at"] and task["completed_at"] < cutoff
        ]
        for batch_id in to_delete:
            del self._tasks[batch_id]
        return len(to_delete)


# 全局批处理器实例
_batch_processor = BatchProcessor()


def get_batch_processor() -> BatchProcessor:
    """获取全局批处理器实例"""
    return _batch_processor
