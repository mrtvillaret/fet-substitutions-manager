import clientApi from './client.js'

export const llegeixAmb = async (client) => (await client.get('/api/settings')).data
export const llegeix = () => llegeixAmb(clientApi)
export const idiomesAmb = async (client) => (await client.get('/api/settings/idiomes')).data
export const idiomes = () => idiomesAmb(clientApi)
export const versionsXmlAmb = async (client) => (await client.get('/api/settings/xml-versions')).data
export const versionsXml = () => versionsXmlAmb(clientApi)
export const logoAmb = async (client, ts) =>
  (await client.get('/api/files/logo', { responseType: 'blob', params: { ts }, _silent: true })).data
export const logo = (ts) => logoAmb(clientApi, ts)
export const editaVersioXmlAmb = async (client, id, cos) =>
  (await client.put(`/api/settings/xml-versions/${id}`, cos)).data
export const editaVersioXml = (id, cos) => editaVersioXmlAmb(clientApi, id, cos)
export const esborraVersioXmlAmb = async (client, id) =>
  (await client.delete(`/api/settings/xml-versions/${id}`)).data
export const esborraVersioXml = (id) => esborraVersioXmlAmb(clientApi, id)
const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }
export const pujaLogoAmb = async (client, formData) =>
  (await client.post('/api/files/upload-logo', formData, multipart)).data
export const pujaLogo = (formData) => pujaLogoAmb(clientApi, formData)
export const desaAmb = async (client, cos) => (await client.put('/api/settings', cos)).data
export const desa = (cos) => desaAmb(clientApi, cos)
export const pujaXmlAmb = async (client, formData) =>
  (await client.post('/api/files/upload-xml', formData, multipart)).data
export const pujaXml = (formData) => pujaXmlAmb(clientApi, formData)
