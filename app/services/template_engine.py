"""
Template Engine for generating YouTube titles and descriptions
"""

from typing import Optional
from app.models.schemas import VideoTask, AffiliateUrl


class TemplateEngine:
    """
    Generates YouTube titles and descriptions from VideoTask data
    """
    
    # Title format: {{prod_code}}-{{prod_name}}-{{prod_short_descr}} ep.{{episode}}
    TITLE_TEMPLATE = "{prod_code}-{prod_name}-{prod_short_descr} ep.{episode}"
    
    # Description template
    DESCRIPTION_TEMPLATE = """{prod_long_descr}

━━━━━━━━━━━━━━━━━━━━━━
🛒 ลิงก์สั่งซื้อ
━━━━━━━━━━━━━━━━━━━━━━
{affiliate_links}
{discount_section}
━━━━━━━━━━━━━━━━━━━━━━
{tags_section}"""
    
    @classmethod
    def generate_title(
        cls,
        prod_code: str,
        prod_name: str,
        prod_short_descr: str,
        episode: int = 1
    ) -> str:
        """
        Generate YouTube title from product info
        
        Format: {{prod_code}}-{{prod_name}}-{{prod_short_descr}} ep.{{episode}}
        Max length: 100 characters
        
        Returns:
            Formatted title (max 100 chars)
        """
        title = cls.TITLE_TEMPLATE.format(
            prod_code=prod_code,
            prod_name=prod_name,
            prod_short_descr=prod_short_descr,
            episode=episode
        )
        
        # Truncate to 100 chars if needed
        if len(title) > 100:
            # Keep prod_code and episode, truncate middle
            base = f"{prod_code}-{prod_name[:20]}... ep.{episode}"
            if len(base) > 100:
                base = f"{prod_code}-... ep.{episode}"
            title = base[:100]
        
        return title
    
    @classmethod
    def generate_title_from_task(cls, task: VideoTask) -> str:
        """Generate title from VideoTask object"""
        return cls.generate_title(
            prod_code=task.prod_code,
            prod_name=task.prod_name,
            prod_short_descr=task.prod_short_descr,
            episode=task.episode
        )
    
    @classmethod
    def format_affiliate_links(cls, urls: list[AffiliateUrl]) -> str:
        """
        Format affiliate links for description
        
        Returns:
            Formatted links string
        """
        if not urls:
            return ""
        
        lines = []
        for url in urls:
            emoji = "🔗" if not url.is_primary else "🛒"
            lines.append(f"{emoji} {url.label}: {url.url}")
        
        return "\n".join(lines)
    
    @classmethod
    def format_discount_section(cls, discount_code: Optional[str]) -> str:
        """Format discount code section"""
        if not discount_code:
            return ""
        
        return f"\n🎁 ใช้โค้ด: {discount_code} รับส่วนลดทันที!\n"
    
    @classmethod
    def format_tags_section(cls, tags: list[str]) -> str:
        """Format tags as hashtags"""
        if not tags:
            return ""
        
        # Format as hashtags
        hashtags = [f"#{tag.replace(' ', '')}" for tag in tags[:15]]  # Max 15 tags
        return " ".join(hashtags)
    
    @classmethod
    def generate_description(
        cls,
        prod_long_descr: str = "",
        aff_urls: list[AffiliateUrl] = None,
        discount_code: Optional[str] = None,
        tags: list[str] = None
    ) -> str:
        """
        Generate YouTube description with affiliate links
        
        Max length: 5000 characters
        
        Returns:
            Formatted description
        """
        affiliate_links = cls.format_affiliate_links(aff_urls or [])
        discount_section = cls.format_discount_section(discount_code)
        tags_section = cls.format_tags_section(tags or [])
        
        description = cls.DESCRIPTION_TEMPLATE.format(
            prod_long_descr=prod_long_descr,
            affiliate_links=affiliate_links,
            discount_section=discount_section,
            tags_section=tags_section
        )
        
        # Clean up empty sections
        description = description.replace("\n\n\n", "\n\n")
        
        # Truncate to 5000 chars if needed
        if len(description) > 5000:
            description = description[:4997] + "..."
        
        return description.strip()
    
    @classmethod
    def generate_description_from_task(cls, task: VideoTask) -> str:
        """Generate description from VideoTask object"""
        return cls.generate_description(
            prod_long_descr=task.prod_long_descr,
            aff_urls=task.aff_urls,
            discount_code=task.discount_code,
            tags=task.prod_tags
        )
    
    @classmethod
    def generate_tags(
        cls,
        prod_tags: list[str] = None,
        custom_tags: list[str] = None
    ) -> list[str]:
        """
        Combine and clean tags for YouTube
        Max 500 characters total, max 30 tags
        
        Returns:
            List of cleaned tags
        """
        all_tags = []
        
        if prod_tags:
            all_tags.extend(prod_tags)
        
        if custom_tags:
            all_tags.extend(custom_tags)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in all_tags:
            tag_clean = tag.strip().lower()
            if tag_clean and tag_clean not in seen:
                seen.add(tag_clean)
                unique_tags.append(tag.strip())
        
        # Limit to 30 tags and 500 chars total
        result = []
        total_chars = 0
        for tag in unique_tags[:30]:
            if total_chars + len(tag) + 1 > 500:  # +1 for comma
                break
            result.append(tag)
            total_chars += len(tag) + 1
        
        return result
    
    @classmethod
    def extract_prod_code_from_title(cls, title: str) -> tuple[Optional[str], Optional[int]]:
        """
        Extract prod_code and episode from YouTube title
        
        Expected format: {{prod_code}}-{{name}}-{{descr}} ep.{{episode}}
        
        Returns:
            (prod_code, episode) or (None, None) if not matched
        """
        try:
            # Try to extract prod_code (first part before -)
            if '-' not in title:
                return None, None
            
            prod_code = title.split('-')[0].strip()
            
            # Try to extract episode
            episode = 1
            if ' ep.' in title.lower():
                ep_part = title.lower().split(' ep.')[-1]
                # Extract number
                ep_num = ''
                for char in ep_part:
                    if char.isdigit():
                        ep_num += char
                    else:
                        break
                if ep_num:
                    episode = int(ep_num)
            
            return prod_code, episode
            
        except Exception:
            return None, None


# Convenience functions
def generate_title(task: VideoTask) -> str:
    """Generate title from VideoTask"""
    return TemplateEngine.generate_title_from_task(task)


def generate_description(task: VideoTask) -> str:
    """Generate description from VideoTask"""
    return TemplateEngine.generate_description_from_task(task)


def generate_tags(task: VideoTask) -> list[str]:
    """Generate tags from VideoTask"""
    return TemplateEngine.generate_tags(task.prod_tags)
