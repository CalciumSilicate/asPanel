"""
数据迁移脚本：为没有 last_startup 的服务器从 asp_logs/latest.log 读取最后修改时间并填充
运行方式: python -m backend.migrations.backfill_last_startup
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.core.database import SessionLocal
from backend.core import models
from backend.core.utils import get_tz_info


def migrate():
    """执行迁移：从 asp_logs/latest.log 读取最后修改时间填充 last_startup"""
    print("开始回填 servers.last_startup 数据...")
    
    db = SessionLocal()
    tz = get_tz_info()
    
    try:
        # 获取所有 last_startup 为空的服务器
        servers = db.query(models.Server).filter(models.Server.last_startup == None).all()
        
        if not servers:
            print("没有需要回填的服务器，所有服务器都已有 last_startup 数据。")
            return
        
        print(f"找到 {len(servers)} 个服务器需要回填 last_startup...")
        
        updated = 0
        skipped = 0
        
        for server in servers:
            server_path = Path(server.path)
            log_file = server_path / "asp_logs" / "latest.log"
            
            if log_file.exists():
                try:
                    # 获取文件最后修改时间
                    mtime = log_file.stat().st_mtime
                    last_startup = datetime.fromtimestamp(mtime, tz=tz)
                    
                    server.last_startup = last_startup
                    db.add(server)
                    updated += 1
                    print(f"  ✓ 服务器 [{server.id}] {server.name}: {last_startup.strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception as e:
                    print(f"  ✗ 服务器 [{server.id}] {server.name}: 读取日志文件失败 - {e}")
                    skipped += 1
            else:
                print(f"  - 服务器 [{server.id}] {server.name}: 日志文件不存在，跳过")
                skipped += 1
        
        db.commit()
        print(f"\n迁移完成: {updated} 个服务器已更新, {skipped} 个跳过")
        
    except Exception as e:
        db.rollback()
        print(f"迁移失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
