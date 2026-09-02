from marklassian import AdfDocument, markdown_to_adf


def convert(markdown: str) -> AdfDocument:
    return markdown_to_adf(markdown, jira_mentions=True)
