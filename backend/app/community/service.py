"""Nghiệp vụ cộng đồng: bài đăng, bảng tin, tim, bình luận, báo cáo."""

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.community.models import Comment, Post, PostLike
from app.community.schemas import CommentOut, PostOut
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.time import aware
from app.memes.models import Meme

PAGE_SIZE = 20
HOT_WINDOW_DAYS = 7
HOT_LIMIT = 50

PostRow = tuple[Post, Meme]


def _visible(query: Select) -> Select:
    return query.join(Meme, Meme.id == Post.meme_id).where(
        Post.hidden.is_(False), Meme.hidden.is_(False), Meme.deleted.is_(False)
    )


def _users(session: Session, ids: set[str]) -> dict[str, User]:
    return {u.id: u for u in session.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


def posts_view(session: Session, rows: list[PostRow], viewer: User | None) -> list[PostOut]:
    """Dữ liệu bài viết kèm tác giả và trạng thái tim của người xem (hai truy vấn cho cả trang)."""
    if not rows:
        return []
    users = _users(session, {p.user_id for p, _ in rows})
    liked: set[str] = set()
    if viewer:
        liked = set(
            session.scalars(
                select(PostLike.post_id).where(
                    PostLike.user_id == viewer.id, PostLike.post_id.in_([p.id for p, _ in rows])
                )
            )
        )
    return [
        PostOut.of(p, m, users.get(p.user_id), liked=p.id in liked, mine=viewer is not None and viewer.id == p.user_id)
        for p, m in rows
    ]


def post_ids(session: Session, meme_ids: list[str]) -> dict[str, str]:
    """meme_id -> post_id cho các meme đã được chia sẻ lên cộng đồng."""
    if not meme_ids:
        return {}
    rows = session.execute(select(Post.meme_id, Post.id).where(Post.meme_id.in_(meme_ids), Post.hidden.is_(False)))
    return dict(rows.all())


def hot_score(post: Post, now: datetime) -> float:
    """Kiểu Hacker News: tương tác chia cho tuổi bài, bình luận nặng hơn tim."""
    hours = (now - aware(post.created_at)).total_seconds() / 3600
    return (post.like_count + 2 * post.comment_count + 1) / math.pow(hours + 2, 1.5)


def get_post(session: Session, post_id: str) -> PostRow:
    row = session.execute(_visible(select(Post, Meme)).where(Post.id == post_id)).first()
    if not row:
        raise ApiError(404, "not_found", "Bài viết không tồn tại hoặc đã bị gỡ")
    return row[0], row[1]


# ---------- bảng tin ----------


def feed_new(session: Session, before: datetime | None) -> tuple[list[PostRow], bool]:
    """Một trang bài mới nhất, kèm cờ còn trang sau."""
    query = _visible(select(Post, Meme))
    if before:
        query = query.where(Post.created_at < before)
    rows = session.execute(query.order_by(Post.created_at.desc()).limit(PAGE_SIZE + 1)).all()
    return [(p, m) for p, m in rows[:PAGE_SIZE]], len(rows) > PAGE_SIZE


def feed_hot(session: Session) -> list[PostRow]:
    now = datetime.now(UTC)
    since = now - timedelta(days=HOT_WINDOW_DAYS)
    rows = session.execute(_visible(select(Post, Meme)).where(Post.created_at >= since)).all()
    return [(p, m) for p, m in sorted(rows, key=lambda r: -hot_score(r[0], now))[:HOT_LIMIT]]


def posts_by(session: Session, username: str) -> list[PostRow]:
    author = session.scalar(select(User).where(User.username == username.lower()))
    if not author or author.is_banned:
        raise ApiError(404, "not_found", "Không tìm thấy người dùng")
    rows = session.execute(
        _visible(select(Post, Meme)).where(Post.user_id == author.id).order_by(Post.created_at.desc()).limit(50)
    )
    return [(p, m) for p, m in rows]


# ---------- bài viết ----------


def create_post(session: Session, user: User, meme_id: str, caption: str) -> PostRow:
    """Mỗi meme chỉ đăng một lần: đăng lại trả về bài cũ."""
    meme = session.get(Meme, meme_id)
    if not meme or meme.deleted:
        raise ApiError(404, "not_found", "Không tìm thấy meme")
    if meme.user_id != user.id:
        raise ApiError(403, "forbidden", "Chỉ chia sẻ được meme do bạn tạo")
    if meme.hidden:
        raise ApiError(403, "hidden", "Meme đang bị báo cáo nên chưa chia sẻ được")
    if meme.rank is None and meme.parent_id is None:
        raise ApiError(400, "invalid_input", "Chỉ chia sẻ được meme kết quả")
    if existing := session.scalar(select(Post).where(Post.meme_id == meme.id)):
        if existing.hidden:
            raise ApiError(403, "hidden", "Bài viết của meme này đã bị gỡ do báo cáo")
        return existing, meme
    post = Post(user_id=user.id, meme_id=meme.id, caption=caption.strip())
    session.add(post)
    try:
        session.commit()
    except IntegrityError:  # bấm đăng hai lần cùng lúc
        session.rollback()
        post = session.scalar(select(Post).where(Post.meme_id == meme.id))
    return post, meme


def edit_post(session: Session, user: User, post_id: str, caption: str) -> PostRow:
    post, meme = get_post(session, post_id)
    if post.user_id != user.id:
        raise ApiError(403, "forbidden", "Chỉ người đăng mới sửa được")
    post.caption = caption.strip()
    post.edited_at = datetime.now(UTC)
    session.commit()
    return post, meme


def delete_post(session: Session, user: User, post_id: str) -> None:
    post = session.get(Post, post_id)
    if not post:
        raise ApiError(404, "not_found", "Bài viết không tồn tại")
    if post.user_id != user.id:
        raise ApiError(403, "forbidden", "Chỉ người đăng mới xoá được")
    remove_posts(session, [post.id])
    session.commit()


def remove_posts(session: Session, ids: list[str]) -> None:
    if not ids:
        return
    session.execute(delete(PostLike).where(PostLike.post_id.in_(ids)))
    session.execute(delete(Comment).where(Comment.post_id.in_(ids)))
    session.execute(delete(Post).where(Post.id.in_(ids)))


def report_post(session: Session, post_id: str) -> None:
    post = session.get(Post, post_id)
    if not post:
        raise ApiError(404, "not_found", "Bài viết không tồn tại")
    post.reported += 1
    if post.reported >= get_settings().report_hide_threshold:
        post.hidden = True
    session.commit()


# ---------- tim ----------


def set_like(session: Session, user: User, post_id: str, liked: bool) -> int:
    """Thả hoặc bỏ tim (gọi lại nhiều lần vẫn đúng). Trả về số tim mới."""
    post, _ = get_post(session, post_id)
    if liked:
        if not session.get(PostLike, (post.id, user.id)):
            session.add(PostLike(post_id=post.id, user_id=user.id))
            try:
                session.flush()
                session.execute(update(Post).where(Post.id == post.id).values(like_count=Post.like_count + 1))
                session.commit()
            except IntegrityError:  # hai lần bấm cùng lúc
                session.rollback()
    else:
        deleted = session.execute(delete(PostLike).where(PostLike.post_id == post.id, PostLike.user_id == user.id))
        if deleted.rowcount:
            session.execute(update(Post).where(Post.id == post.id).values(like_count=Post.like_count - 1))
        session.commit()
    session.refresh(post)
    return post.like_count


# ---------- bình luận ----------


def comments_view(session: Session, post: Post, viewer: User | None) -> list[CommentOut]:
    comments = session.scalars(
        select(Comment).where(Comment.post_id == post.id).order_by(Comment.created_at).limit(200)
    ).all()
    users = _users(session, {c.user_id for c in comments})
    return [
        # chủ bình luận và chủ bài đều xoá được
        CommentOut.of(c, users.get(c.user_id), can_delete=viewer is not None and viewer.id in (c.user_id, post.user_id))
        for c in comments
    ]


def add_comment(session: Session, user: User, post_id: str, body: str) -> Comment:
    post, _ = get_post(session, post_id)
    text = " ".join(body.split())
    if not text:
        raise ApiError(400, "invalid_input", "Bình luận không được để trống")
    comment = Comment(post_id=post.id, user_id=user.id, body=text)
    session.add(comment)
    session.execute(update(Post).where(Post.id == post.id).values(comment_count=Post.comment_count + 1))
    session.commit()
    return comment


def delete_comment(session: Session, user: User, comment_id: str) -> None:
    comment = session.get(Comment, comment_id)
    if not comment:
        raise ApiError(404, "not_found", "Bình luận không tồn tại")
    post = session.get(Post, comment.post_id)
    if user.id not in (comment.user_id, post.user_id if post else None):
        raise ApiError(403, "forbidden", "Bạn không xoá được bình luận này")
    session.delete(comment)
    if post:
        session.execute(update(Post).where(Post.id == post.id).values(comment_count=Post.comment_count - 1))
    session.commit()


# ---------- theo người dùng ----------


def user_stats(session: Session, user_id: str) -> tuple[int, int]:
    """(số bài đăng, tổng số tim nhận được)."""
    posts = session.scalar(select(func.count()).select_from(Post).where(Post.user_id == user_id)) or 0
    likes = session.scalar(select(func.sum(Post.like_count)).where(Post.user_id == user_id)) or 0
    return posts, likes


def purge_user(session: Session, user_id: str) -> None:
    """Khi xoá tài khoản: bài của người này biến mất cùng tim và bình luận;
    tim/bình luận của họ ở bài người khác cũng xoá và đếm lại."""
    remove_posts(session, list(session.scalars(select(Post.id).where(Post.user_id == user_id))))
    touched = set(session.scalars(select(PostLike.post_id).where(PostLike.user_id == user_id)))
    touched |= set(session.scalars(select(Comment.post_id).where(Comment.user_id == user_id)))
    session.execute(delete(PostLike).where(PostLike.user_id == user_id))
    session.execute(delete(Comment).where(Comment.user_id == user_id))
    for post in session.scalars(select(Post).where(Post.id.in_(touched))):
        post.like_count = session.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post.id))
        post.comment_count = session.scalar(select(func.count()).select_from(Comment).where(Comment.post_id == post.id))
