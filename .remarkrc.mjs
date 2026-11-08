import remarkGfm from 'remark-gfm'
import remarkLint from 'remark-lint'
import noUndefinedReferences from 'remark-lint-no-undefined-references'
import noUnusedDefinitions from 'remark-lint-no-unused-definitions'
import noDuplicateDefinitions from 'remark-lint-no-duplicate-definitions'
import noInlinePadding from 'remark-lint-no-inline-padding'
import blockquoteIndentation from 'remark-lint-blockquote-indentation'
import checkboxContentIndent from 'remark-lint-checkbox-content-indent'
import finalNewline from 'remark-lint-final-newline'
import listItemBulletIndent from 'remark-lint-list-item-bullet-indent'
import listItemIndent from 'remark-lint-list-item-indent'
import noAutoLinkWithoutProtocol from 'remark-lint-no-auto-link-without-protocol'
import noBlockquoteWithoutMarker from 'remark-lint-no-blockquote-without-marker'
import noLiteralUrls from 'remark-lint-no-literal-urls'
import noHeadingContentIndent from 'remark-lint-no-heading-content-indent'
import hardBreakSpaces from 'remark-lint-hard-break-spaces'
import codeBlockStyle from 'remark-lint-code-block-style'
import tableCellPadding from 'remark-lint-table-cell-padding'
import tablePipes from 'remark-lint-table-pipes'
import checkboxCharacterStyle from 'remark-lint-checkbox-character-style'
import definitionCase from 'remark-lint-definition-case'
import emphasisMarker from 'remark-lint-emphasis-marker'
import strongMarker from 'remark-lint-strong-marker'
import unorderedListMarkerStyle from 'remark-lint-unordered-list-marker-style'
import fencedCodeMarker from 'remark-lint-fenced-code-marker'
import ruleStyle from 'remark-lint-rule-style'
import validateLinks from 'remark-validate-links'

export default {
  plugins: [
    remarkGfm,
    remarkLint,
    noUndefinedReferences, noUnusedDefinitions, noDuplicateDefinitions, noInlinePadding,
    [blockquoteIndentation, 2], checkboxContentIndent,
    [emphasisMarker, '_'], [strongMarker, '*'], finalNewline,
    [unorderedListMarkerStyle, '-'], listItemBulletIndent, [listItemIndent, 'one'],
    [fencedCodeMarker, '`'], [ruleStyle, '---'],
    noAutoLinkWithoutProtocol, noBlockquoteWithoutMarker, noLiteralUrls,
    noHeadingContentIndent, hardBreakSpaces, [codeBlockStyle, 'fenced'],
    [tableCellPadding, 'padded'], tablePipes,
    [checkboxCharacterStyle, { checked: 'x', unchecked: ' ' }], definitionCase,
    [validateLinks, { repository: 'https://github.com/Zero-State-LLC/Psy-Fi' }]
  ]
}
