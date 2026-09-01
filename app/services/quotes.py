"""A small, self-contained pool of quotes for the wall dashboard — no external API, so the
screen still shows something on a host with no internet egress. Picked deterministically by
day-of-year so the whole household sees the same one all day, and it changes on its own
tomorrow with no scheduler needed.
"""

from datetime import date

QUOTES: list[tuple[str, str]] = [
    ("Many hands make light work.", "Proverb"),
    ("Alone we can do so little; together we can do so much.", "Helen Keller"),
    ("The best way to find yourself is to lose yourself in the service of others.", "Mahatma Gandhi"),
    (
        "Coming together is a beginning; keeping together is progress; working together is success.",
        "Henry Ford",
    ),
    ("A journey of a thousand miles begins with a single step.", "Lao Tzu"),
    ("Small deeds done are better than great deeds planned.", "Peter Marshall"),
    ("Teamwork makes the dream work.", "John C. Maxwell"),
    ("Gratitude turns what we have into enough.", "Anonymous"),
    ("The best time to plant a tree was 20 years ago. The second best time is now.", "Chinese proverb"),
    ("It always seems impossible until it's done.", "Nelson Mandela"),
    ("Well done is better than well said.", "Benjamin Franklin"),
    ("Do small things with great love.", "Mother Teresa"),
    ("Kindness is a language which the deaf can hear and the blind can see.", "Mark Twain"),
    ("No act of kindness, no matter how small, is ever wasted.", "Aesop"),
    (
        "The strength of the team is each individual member. The strength of each member is the team.",
        "Phil Jackson",
    ),
    ("United we stand, divided we fall.", "Aesop"),
    ("Home is the nicest word there is.", "Laura Ingalls Wilder"),
    ("A little progress each day adds up to big results.", "Anonymous"),
    ("The family is one of nature's masterpieces.", "George Santayana"),
    ("Where we love is home.", "Oliver Wendell Holmes Sr."),
    ("Great things are done by a series of small things brought together.", "Vincent van Gogh"),
    ("You don't have to see the whole staircase, just take the first step.", "Martin Luther King Jr."),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("If you want to go fast, go alone. If you want to go far, go together.", "African proverb"),
]


def quote_of_the_day(on_date: date) -> dict:
    text, author = QUOTES[on_date.toordinal() % len(QUOTES)]
    return {"text": text, "author": author}
