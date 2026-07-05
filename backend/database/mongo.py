import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class DevPilotDB:
    def __init__(self):
        client = MongoClient(os.getenv("MONGODB_URL"))
        db = client["devpilot_ai"]

        # Collections
        self.reviews = db["reviews"]
        self.security_issues = db["security_issues"]
        self.analytics = db["analytics"]
        self.pr_tracking = db["pr_tracking"]

    def get_last_reviewed_sha(self, pr_url: str) -> str | None:
        doc = self.pr_tracking.find_one({"pr_url": pr_url})
        return doc.get("last_sha") if doc else None

    def set_last_reviewed_sha(self, pr_url: str, sha: str):
        self.pr_tracking.update_one(
            {"pr_url": pr_url},
            {"$set": {"pr_url": pr_url, "last_sha": sha, "updated_at": datetime.now()}},
            upsert=True
        )

    def save_review(self, pr_data: dict, result: dict) -> str:
        """Save complete PR review"""
        doc = {
            "pr_title": pr_data.get("pr_title"),
            "pr_url": pr_data.get("pr_url"),
            "filename": pr_data.get("filename"),
            "score": result.get("overall_score"),
            "is_safe": result.get("security_result", {}).get("is_safe", True),
            "vulnerabilities": result.get("security_result", {}).get("vulnerabilities", []),
            "issues": result.get("review_result", {}).get("issues", []),
            "blocked": result.get("should_block_merge"),
            "severity": result.get("severity_level"),
            "summary": result.get("final_summary"),
            "generated_tests": result.get("generated_tests"),
            "fixed_code": result.get("fixed_code"),
            "doc_summary": result.get("doc_summary"),
            "created_at": datetime.now()
        }
        inserted = self.reviews.insert_one(doc)
        print(f"✅ Saved to MongoDB: {inserted.inserted_id}")
        return str(inserted.inserted_id)

    def get_analytics(self) -> dict:
        """Dashboard stats"""
        total = self.reviews.count_documents({})
        blocked = self.reviews.count_documents({"blocked": True})
        unsafe = self.reviews.count_documents({"is_safe": False})
        
        avg = list(self.reviews.aggregate([
            {"$group": {"_id": None, "avg": {"$avg": "$score"}}}
        ]))
        
        # FIXED: Added [0] index to avoid list-access TypeError crash
        return {
            "total_reviews": total,
            "blocked_prs": blocked,
            "security_issues": unsafe,
            "average_score": round(avg[0]["avg"], 1) if avg else 0,
            "approval_rate": round(((total - blocked) / total * 100), 1) if total > 0 else 0
        }

    def get_recent_reviews(self, limit: int = 10) -> list:
        """Get recent reviews for history table"""
        reviews = list(
            self.reviews.find({}, {"_id": 0})
            .sort("created_at", -1)
            .limit(limit)
        )
        # Convert datetime to string for clean serialization
        for r in reviews:
            if "created_at" in r and isinstance(r["created_at"], datetime):
                r["created_at"] = r["created_at"].isoformat() + "Z"
        return reviews
    def delete_all_reviews(self) -> dict:
        reviews_result = self.reviews.delete_many({})
        security_result = self.security_issues.delete_many({})
        analytics_result = self.analytics.delete_many({})
        total = reviews_result.deleted_count + security_result.deleted_count + analytics_result.deleted_count
        print(f"🗑️ Deleted {total} document(s) across all collections")
        return {
            "deleted_count": total,
            "reviews_deleted": reviews_result.deleted_count,
            "security_issues_deleted": security_result.deleted_count,
            "analytics_deleted": analytics_result.deleted_count
    }

if __name__ == "__main__":
    db = DevPilotDB()
    print("✅ MongoDB connected!")
    print("Analytics:", db.get_analytics())
