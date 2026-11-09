// Qualsevol presentació d'un error capturat passa per la mateixa regla.
export default {
  meta: {
    type: 'problem',
    schema: [],
    messages: { unic: 'Mostra l’error amb avisaError(error, () => ...), perquè només s’avisi una vegada.' },
  },
  create(context) {
    const comprova = (node) => {
      const ancestres = context.sourceCode.getAncestors(node)
      const captura = ancestres.findLast(n => n.type === 'CatchClause')
      if (!captura) return
      const nom = captura.param?.name
      const gestionat = nom && ancestres.some(n =>
        n.type === 'CallExpression' && n.callee.type === 'Identifier' && n.callee.name === 'avisaError' &&
        n.arguments[0]?.type === 'Identifier' && n.arguments[0].name === nom)
      if (!gestionat) context.report({ node, messageId: 'unic' })
    }
    return {
      CallExpression(node) {
        if (node.callee.type !== 'MemberExpression' || node.callee.property.name !== 'add') return
        const opcions = node.arguments[0]
        if (opcions?.type === 'ObjectExpression' && opcions.properties.some(p => (p.key?.name || p.key?.value) === 'severity')) comprova(node)
      },
      AssignmentExpression(node) {
        const camp = node.left
        if (camp.type !== 'MemberExpression' || camp.property.name !== 'value' ||
          !['errorMessage', 'error', 'errorCarregaSubstitucions', 'loginError'].includes(camp.object?.name)) return
        if (node.right.type === 'Literal' && !node.right.value) return
        comprova(node)
      },
    }
  },
}
