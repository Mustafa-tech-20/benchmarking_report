"""
Image Section Generation for Enhanced Reports
Generates PDF-style image galleries for car comparison reports
"""

from typing import Dict, Any, List


def generate_hero_section(comparison_data: Dict[str, Any]) -> str:
    """
    Generate hero section with car images at the top of the report.

    Args:
        comparison_data: Dict mapping car names to their scraped data

    Returns:
        HTML string for hero section
    """
    car_names = []
    hero_images = []

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            car_names.append(car_name)
            images = car_data.get("images") or {}
            hero_imgs = images.get("hero", [])
            if hero_imgs:
                # Handle multiple formats: list, tuple, or string
                first_img = hero_imgs[0]
                if isinstance(first_img, (list, tuple)) and len(first_img) >= 1:
                    img_url = first_img[0]
                    if img_url and isinstance(img_url, str):
                        hero_images.append(img_url)
                    else:
                        hero_images.append("")
                elif isinstance(first_img, str):
                    hero_images.append(first_img)
                else:
                    hero_images.append("")
            else:
                hero_images.append("")  # Placeholder

    if not car_names:
        return ""

    # Generate title
    if len(car_names) == 1:
        title = f"{car_names[0].upper()} - DETAILED ANALYSIS"
    elif len(car_names) == 2:
        title = f"{car_names[0].upper()} & {car_names[1].upper()}"
    else:
        title = " | ".join([name.upper() for name in car_names[:3]])

    # Generate image grid
    image_html = ""
    for i, (name, img_url) in enumerate(zip(car_names, hero_images)):
        if img_url:
            image_html += f'''
            <div class="hero-car-card">
                <img src="{img_url}" alt="{name}" onerror="this.style.display='none'">
                <div class="hero-car-name">{name}</div>
            </div>
            '''

    # Conditional subtitle based on number of cars
    subtitle_text = "SPEC & FEATURES ANALYSIS" if len(car_names) == 1 else "SPEC & FEATURES COMPARISON"

    html = f'''
    <div class="hero-section">
        <div class="hero-content">
            <h1 class="hero-title">{title}</h1>
            <p class="hero-subtitle">2025 COMPREHENSIVE BENCHMARKING REPORT</p>
            <div class="hero-divider"></div>
            <p class="hero-description">{subtitle_text}</p>
        </div>
        <div class="hero-images-grid">
            {image_html}
        </div>
    </div>
    '''

    return html


def generate_image_gallery_section(
    title: str,
    comparison_data: Dict[str, Any],
    image_category: str,
    section_id: str = ""
) -> str:
    """
    Generate an image gallery section for a specific category.

    Args:
        title: Section title (e.g., "Exterior Highlights")
        comparison_data: Dict mapping car names to their scraped data
        image_category: Category key in images dict ("exterior", "interior", etc.)
        section_id: Optional HTML id for the section

    Returns:
        HTML string for image gallery section
    """
    # Collect all images from all cars for this category
    all_images = []

    for car_name, car_data in comparison_data.items():
        if isinstance(car_data, dict) and "error" not in car_data:
            images = car_data.get("images") or {}
            category_images = images.get(image_category, [])

            # Handle multiple formats: list, tuple, or string
            for img_item in category_images:
                img_url = None
                feature_caption = image_category.title()

                if isinstance(img_item, (list, tuple)) and len(img_item) >= 1:
                    # Format: [url, caption] or (url, caption)
                    img_url = img_item[0]
                    if len(img_item) >= 2:
                        feature_caption = img_item[1]
                elif isinstance(img_item, str):
                    # Fallback for simple URL format
                    img_url = img_item

                # Add all valid image URLs
                if img_url and isinstance(img_url, str):
                    all_images.append({
                        "url": img_url,
                        "feature": feature_caption,  # e.g., "Headlights"
                        "car_name": car_name,        # e.g., "Mahindra Thar"
                        "alt": f"{car_name} {feature_caption}"
                    })

    if not all_images:
        return ""  # Don't show section if no images

    # Generate image grid
    images_html = ""
    for img_data in all_images[:12]:  # Max 12 images per section
        images_html += f'''
        <div class="gallery-item">
            <img src="{img_data['url']}" alt="{img_data['alt']}"
                 onerror="this.parentElement.style.display='none'">
            <div class="gallery-feature">{img_data['feature']}</div>
            <div class="gallery-car-name">{img_data['car_name']}</div>
        </div>
        '''

    id_attr = f'id="{section_id}"' if section_id else ""

    html = f'''
    <div class="content image-gallery-section" {id_attr}>
        <div class="section-header">
            <div class="icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                </svg>
            </div>
            <h2>{title}</h2>
        </div>
        <div class="image-gallery">
            {images_html}
        </div>
    </div>
    '''

    return html


def get_image_section_styles() -> str:
    """
    Returns CSS styles for image sections.
    """
    return '''
    /* Hero Section Styles */
    .hero-section {
        background: linear-gradient(135deg, #2E3B4E 0%, #1c2a39 100%);
        padding: 60px 40px;
        margin: -20px -20px 40px -20px;
        border-radius: 0;
        position: relative;
        overflow: hidden;
    }

    .hero-section::before {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        width: 50%;
        height: 100%;
        background: linear-gradient(135deg, rgba(221, 3, 43, 0.1) 0%, transparent 100%);
    }

    .hero-content {
        position: relative;
        z-index: 2;
        text-align: center;
        margin-bottom: 40px;
    }

    .hero-title {
        font-size: 42px;
        font-weight: 800;
        color: white;
        margin: 0 0 15px 0;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    .hero-subtitle {
        font-size: 16px;
        color: #dd032b;
        font-weight: 600;
        margin: 0 0 20px 0;
        letter-spacing: 3px;
    }

    .hero-divider {
        width: 80px;
        height: 3px;
        background: #dd032b;
        margin: 0 auto 20px auto;
    }

    .hero-description {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.8);
        margin: 0;
        letter-spacing: 2px;
    }

    .hero-images-grid {
        position: relative;
        z-index: 2;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 30px;
        max-width: 1200px;
        margin: 0 auto;
    }

    .hero-car-card {
        background: white;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        transition: transform 0.3s ease;
    }

    .hero-car-card:hover {
        transform: translateY(-5px);
    }

    .hero-car-card img {
        width: 100%;
        height: 220px;
        object-fit: cover;
        display: block;
    }

    .hero-car-name {
        padding: 20px;
        text-align: center;
        font-size: 18px;
        font-weight: 700;
        color: #2E3B4E;
        background: white;
    }

    /* Image Gallery Section Styles */
    .image-gallery-section {
        margin-top: 40px;
    }

    .image-gallery {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 25px;
        padding: 20px 0;
    }

    .gallery-item {
        background: white;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        cursor: pointer;
    }

    .gallery-item:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    }

    .gallery-item img {
        width: 100%;
        height: 200px;
        object-fit: cover;
        display: block;
    }

    .gallery-feature {
        padding: 12px 15px 8px 15px;
        text-align: center;
        font-size: 13px;
        font-weight: 700;
        color: #1c2a39;
        background: #f8f9fa;
        line-height: 1.3;
    }

    .gallery-car-name {
        padding: 0 15px 12px 15px;
        text-align: center;
        font-size: 11px;
        font-weight: 500;
        color: #6c757d;
        background: #f8f9fa;
    }

    /* Print Styles for Images */
    @media print {
        .hero-section {
            page-break-after: always;
            margin: 0;
            padding: 40px 20px;
            break-after: page;
        }

        .hero-car-card {
            page-break-inside: avoid;
            break-inside: avoid;
        }

        .hero-car-card img {
            width: 100% !important;
            height: auto !important;
            max-height: 200px !important;
            object-fit: contain !important;
            display: block;
            margin: 0 auto;
        }

        .image-gallery {
            display: grid !important;
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 10px !important;
            page-break-inside: auto !important;
        }

        .gallery-item {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            margin-bottom: 10px !important;
            box-shadow: none !important;
            border: 1px solid #ddd !important;
        }

        /* Force page break after every 6 items (2x3 grid) */
        .gallery-item:nth-child(6n) {
            page-break-after: always !important;
            break-after: page !important;
        }

        .gallery-item img {
            width: 100% !important;
            height: 180px !important;
            max-height: 180px !important;
            object-fit: contain !important;
            display: block;
            margin: 0 auto;
            background: #f8f9fa;
        }

        .image-gallery-section {
            page-break-before: auto;
            page-break-after: auto;
            page-break-inside: auto;
            break-before: auto;
            break-after: auto;
            break-inside: auto;
            margin-bottom: 0;
        }

        .section-header {
            page-break-after: avoid;
            break-after: avoid;
        }

        .gallery-feature,
        .gallery-car-name {
            page-break-inside: avoid !important;
            break-inside: avoid !important;
            text-align: center;
            font-size: 10px !important;
            padding: 6px 8px !important;
        }
    }

    /* Mobile Responsive */
    @media (max-width: 768px) {
        .hero-title {
            font-size: 28px;
        }

        .hero-subtitle {
            font-size: 12px;
        }

        .hero-images-grid {
            grid-template-columns: 1fr;
            gap: 20px;
        }

        .image-gallery {
            grid-template-columns: 1fr;
            gap: 15px;
        }

        .gallery-item img {
            height: 180px;
        }
    }
    '''
