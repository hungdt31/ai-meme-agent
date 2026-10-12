"""Tạo embedding cho template mới hoặc vừa sửa mô tả. Chạy lại mỗi khi thêm template.

python -m scripts.index_templates
"""

from rag.search import get_index


def main():
    index = get_index()
    added = index.build()
    print(f"Embedded {added} template(s); index has {len(index.vectors)} vectors -> {index.index_path}")


if __name__ == "__main__":
    main()
