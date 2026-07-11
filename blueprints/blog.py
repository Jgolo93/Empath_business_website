import hashlib

from flask import Blueprint, jsonify, render_template, request

from extensions import db
from models import BlogLike, BlogPostStats, PageView

blog_bp = Blueprint('blog', __name__)

STATIC_POST_TEMPLATES = {
    'cybersecurity-tips-small-business': 'blog_cybersecurity_tips.html',
    'it-solutions-productivity-boost': 'blog_productivity_boost.html',
    'glens-grass-case-study': 'blog_glens_grass_case_study.html',
    'world-of-testing': 'blog_world_of_testing.html',
    'robot-framework-browser-library': 'blog_robot_framework.html',
}


@blog_bp.route('/blog')
def blog():
    return render_template('blog.html')


@blog_bp.route('/blog/cybersecurity-tips-small-business')
def cybersecurity_tips():
    return render_template('blog_cybersecurity_tips.html')


@blog_bp.route('/blog/it-solutions-productivity-boost')
def productivity_boost():
    return render_template('blog_productivity_boost.html')


@blog_bp.route('/blog/glens-grass-case-study')
def glens_grass_case_study():
    return render_template('blog_glens_grass_case_study.html')


@blog_bp.route('/blog/world-of-testing')
def world_of_testing():
    return render_template('blog_world_of_testing.html')


@blog_bp.route('/blog/robot-framework-browser-library')
def robot_framework_browser_library():
    return render_template('blog_robot_framework.html')


@blog_bp.route('/blog/<slug>')
def blog_post(slug):
    try:
        stat = BlogPostStats.query.filter_by(post_slug=slug).first()
        view_count = stat.view_count if stat else 0
        like_count = BlogLike.query.filter_by(post_slug=slug).count()
    except Exception:
        view_count = 0
        like_count = 0

    template = STATIC_POST_TEMPLATES.get(slug)
    if template:
        return render_template(template, view_count=view_count, like_count=like_count)
    return render_template('blog.html')


def _client_ip():
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_address and ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    return ip_address


def _user_agent_hash():
    user_agent = request.headers.get('User-Agent', '')
    return hashlib.sha256(user_agent.encode()).hexdigest()[:64]


@blog_bp.route('/api/blog/like', methods=['POST'])
def like_blog_post():
    try:
        data = request.get_json()
        post_slug = data.get('post_slug')
        if not post_slug:
            return jsonify({'success': False, 'error': 'Post slug is required'}), 400
        ip_address = _client_ip()
        user_agent_hash = _user_agent_hash()
        existing = BlogLike.query.filter_by(post_slug=post_slug, ip_address=ip_address, user_agent_hash=user_agent_hash).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
            count = BlogLike.query.filter_by(post_slug=post_slug).count()
            return jsonify({'success': True, 'liked': False, 'count': count}), 200
        like = BlogLike(post_slug=post_slug, ip_address=ip_address, user_agent_hash=user_agent_hash)
        db.session.add(like)
        db.session.commit()
        count = BlogLike.query.filter_by(post_slug=post_slug).count()
        return jsonify({'success': True, 'liked': True, 'count': count}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@blog_bp.route('/api/blog/likes/<post_slug>', methods=['GET'])
def get_blog_likes(post_slug):
    try:
        count = BlogLike.query.filter_by(post_slug=post_slug).count()
        has_liked = BlogLike.query.filter_by(post_slug=post_slug, ip_address=_client_ip(), user_agent_hash=_user_agent_hash()).first() is not None
        return jsonify({'success': True, 'count': count, 'hasLiked': has_liked}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@blog_bp.route('/api/blog/view/<post_slug>', methods=['POST'])
def track_blog_view(post_slug):
    try:
        referrer = request.headers.get('Referer', '')
        view = PageView(page_path=f'/blog/{post_slug}', ip_address=_client_ip(), user_agent=request.headers.get('User-Agent', ''), referrer=referrer)
        db.session.add(view)
        db.session.commit()
        stat = BlogPostStats.query.filter_by(post_slug=post_slug).first()
        if stat:
            stat.view_count += 1
        else:
            stat = BlogPostStats(post_slug=post_slug, view_count=1)
            db.session.add(stat)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@blog_bp.route('/api/blog/stats/<post_slug>', methods=['GET'])
def get_blog_stats(post_slug):
    try:
        likes = BlogLike.query.filter_by(post_slug=post_slug).count()
        stat = BlogPostStats.query.filter_by(post_slug=post_slug).first()
        views = stat.view_count if stat else 0
        return jsonify({'success': True, 'likes': likes, 'views': views}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
