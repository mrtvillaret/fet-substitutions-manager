<template>
  <div class="grups-view">
    <div class="view-header">
      <h2>{{ $t('groups.title') }}</h2>
      <p class="subtitle">{{ dataFormatada }}</p>
      <p class="instructions">
        {{ $t('groups.instructionsLine1') }}
        {{ $t('groups.instructionsLine2') }}
      </p>
      <p class="instructions">{{ $t('groups.instructionsTeachers') }}</p>
    </div>

    <!-- Carregant -->
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem;"></i>
      <p>{{ $t('common.loadingConfig') }}</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-message">
      <Message severity="error" :closable="false">{{ error }}</Message>
    </div>

    <!-- Dia sense classes (p.ex. cap de setmana) -->
    <div v-else-if="!hores.length" class="error-message">
      <Message severity="info" :closable="false">{{ $t('groups.noClassesDay') }}</Message>
    </div>

    <!-- Main Content -->
    <div v-else>
      <!-- Toolbar -->
      <div class="toolbar">
        <div class="actions-group">
          <Button :label="$t('groups.all')" @click="marcarTots" severity="secondary" size="small" />
          <Button :label="$t('groups.none')" @click="desmarcarTots" severity="secondary" size="small" outlined />
        </div>

        <div class="save-actions">
          <Tag v-if="teCanvis" severity="warning" :value="$t('common.unsavedChanges')" class="unsaved-tag"></Tag>
          <Button
            :label="$t('common.save')"
            @click="desarGrups"
            severity="success"
            :disabled="!teCanvis"
            :loading="desant"
          />
        </div>
      </div>

      <!-- Editor Card -->
      <div class="content-card">
        <!-- Professors alliberats (sense alliberar el seu grup) -->
        <div v-if="resumProfessors.length" class="teachers-summary">
          <span class="teachers-summary-label">{{ $t('groups.teachersTitle') }}:</span>
          <Chip
            v-for="item in resumProfessors"
            :key="item.professor"
            :label="`${item.professor} (${item.hores.join(', ')})`"
            removable
            @remove="treureProfessor(item.professor)"
          />
        </div>

        <!-- Taula de checkboxes -->
        <div class="table-container">
          <table class="grups-table">
            <thead>
              <tr>
                <th class="grup-col">{{ $t('groups.groupClass') }}</th>
                <th v-for="hora in hores" :key="hora" class="hora-col">{{ hora }}</th>
              </tr>
            </thead>
            <tbody>
              <!-- Activitats alliberables (configurades a Prioritats) -->
              <template v-if="activitatsNoms.length || activitatsPerDefecte.length">
                <tr class="section-row">
                  <td :colspan="hores.length + 1">{{ $t('groups.activitiesHeader') }}</td>
                </tr>
                <!-- Alliberades fins que tenen alumnes (p.ex. Reforç): es gestionen per franges -->
                <tr v-for="act in activitatsPerDefecte" :key="`perdef-${act}`">
                  <td class="grup-name"><span>{{ act }}</span></td>
                  <td :colspan="hores.length" class="perdef-cell">
                    <span>{{ $t('groups.reforcRowHint') }}</span>
                    <Button
                      :label="$t('groups.reforcManage')"
                      icon="pi pi-users"
                      size="small"
                      severity="info"
                      outlined
                      @click="obrirReforc(act)"
                    />
                  </td>
                </tr>
                <!-- Reforços d'aquell dia: qui és lliure i qui es pot alliberar només aquell dia -->
                <tr v-for="act in activitatsPerDefecte.filter(a => reforcsDelDia[a])" :key="`perdef-avui-${act}`">
                  <td class="grup-name reforc-avui-nom">{{ $t('groups.reforcTodayRow') }}</td>
                  <td v-for="hora in hores" :key="`perdef-avui-${act}-${hora}`" class="checkbox-cell">
                    <button
                      v-if="professorsReforcAvui(act, hora).length"
                      type="button"
                      class="teachers-btn"
                      :class="{ active: alliberatsReforcAvui(act, hora).length }"
                      :title="$t('groups.reforcTodayTitle')"
                      :aria-label="$t('groups.reforcTodayTitle')"
                      @click="obrirProfessors($event, 'reforc', act, hora)"
                    >
                      <i class="pi pi-user"></i>
                      <span>{{ lliuresReforcAvui(act, hora) }}/{{ professorsReforcAvui(act, hora).length }}</span>
                    </button>
                  </td>
                </tr>
                <tr v-for="act in activitatsNoms" :key="`act-${act}`">
                  <td class="grup-name"><span>{{ act }}</span></td>
                  <td v-for="hora in hores" :key="`act-${act}-${hora}`" class="checkbox-cell">
                    <div v-if="professorsActivitat(act, hora).length" class="cell-inner">
                      <Checkbox :aria-label="`${act} · ${hora}`" v-model="activitatsMarcades[act][hora]" :binary="true" />
                      <button
                        v-if="!activitatsMarcades[act][hora]"
                        type="button"
                        class="teachers-btn"
                        :class="{ active: alliberatsActivitat(act, hora).length }"
                        :title="$t('groups.freeTeachersTitle')"
                        :aria-label="$t('groups.freeTeachersTitle')"
                        @click="obrirProfessors($event, 'activitat', act, hora)"
                      >
                        <i class="pi pi-user"></i>
                        <span v-if="alliberatsActivitat(act, hora).length">{{ alliberatsActivitat(act, hora).length }}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
              <!-- Separació amb els grups, amb la seva pròpia fila d'hores -->
              <tr v-if="activitatsNoms.length || activitatsPerDefecte.length" class="section-row section-hours">
                <td>{{ $t('groups.groupsHeader') }}</td>
                <td v-for="hora in hores" :key="`sep-${hora}`">{{ hora }}</td>
              </tr>
              <tr v-for="grup in grupsDisponibles" :key="grup">
                <td class="grup-name" @click="toggleGrupComplet(grup)">
                  <span class="clickable">{{ grup }}</span>
                </td>
                <td v-for="hora in hores" :key="`${grup}-${hora}`" class="checkbox-cell">
                  <div class="cell-inner">
                    <Checkbox
                      :aria-label="`${grup} · ${hora}`" v-model="checkboxes[grup][hora]"
                      :binary="true"
                      @change="onCheckboxChange"
                    />
                    <button
                      v-if="professorsDe(grup, hora).length && !checkboxes[grup][hora]"
                      type="button"
                      class="teachers-btn"
                      :class="{ active: alliberatsDe(grup, hora).length }"
                      :title="$t('groups.freeTeachersTitle')"
                      :aria-label="$t('groups.freeTeachersTitle')"
                      @click="obrirProfessors($event, 'grup', grup, hora)"
                    >
                      <i class="pi pi-user"></i>
                      <span v-if="alliberatsDe(grup, hora).length">{{ alliberatsDe(grup, hora).length }}</span>
                    </button>
                  </div>
                </td>
              </tr>

            </tbody>
          </table>
        </div>

        <!-- Resum -->
        <div class="summary">
          <Tag severity="info" :value="$t('groups.summary', { groups: totalGrupsSeleccionats, hours: totalHoresSeleccionades })"></Tag>
        </div>
      </div>
    </div>

    <!-- Professors d'una franja: alliberar-ne només alguns -->
    <OverlayPanel ref="panellProfessors">
      <div v-if="franja" class="teachers-panel">
        <strong>{{ franja.nom }} · {{ franja.hora }}</strong>
        <p class="teachers-panel-hint">{{ $t('groups.teachersHint') }}</p>
        <div v-for="prof in professorsFranja(franja)" :key="prof" class="teachers-panel-row">
          <!-- Reforç sense alumnes: lliure per defecte; desmarcar = aquell dia sí que en té -->
          <Checkbox
            v-if="franja.tipus === 'reforc' && !reforcAmbAlumnes(franja.nom, franja.hora, prof)"
            :inputId="`prof-${prof}`"
            :modelValue="!estaOcupat(prof, franja.hora)"
            :binary="true"
            @update:modelValue="valor => marcaOcupat(prof, franja.hora, !valor)"
          />
          <Checkbox
            v-else
            :inputId="`prof-${prof}`"
            :modelValue="estaAlliberat(prof, franja.hora)"
            :binary="true"
            @update:modelValue="valor => marcaProfessor(prof, franja.hora, valor)"
          />
          <label :for="`prof-${prof}`">{{ prof }}</label>
          <small v-if="franja.tipus === 'reforc'" class="reforc-estat">
            {{ reforcAmbAlumnes(franja.nom, franja.hora, prof) ? $t('groups.reforcBusy') : $t('groups.reforcFreeNoStudents') }}
          </small>
        </div>
        <p v-if="franja.tipus === 'reforc'" class="teachers-panel-hint" style="margin-top: 0.5rem;">
          {{ $t('groups.reforcTodayHint') }}
        </p>
      </div>
    </OverlayPanel>

    <!-- Reforços (activitats alliberades fins que tenen alumnes): franges amb alumnes -->
    <Dialog
      v-model:visible="reforc.visible"
      :header="$t('groups.reforcTitle', { activitat: reforc.activitat })"
      modal
      :style="{ width: reforc.vista === 'setmana' ? '60rem' : '44rem', maxWidth: '96vw' }"
    >
      <p class="reforc-hint">{{ $t('groups.reforcHint') }}</p>
      <div class="reforc-toolbar">
        <div class="reforc-vista">
          <Button :label="$t('groups.reforcViewTeacher')" size="small"
                  :outlined="reforc.vista !== 'professor'" @click="reforc.vista = 'professor'" />
          <Button :label="$t('groups.reforcViewWeek')" size="small"
                  :outlined="reforc.vista !== 'setmana'" @click="reforc.vista = 'setmana'" />
        </div>
        <Dropdown :filterInputProps="{ 'aria-label': $t('common.filterOptions') }" :aria-label="$t('groups.reforcPickTeacher')"
          v-if="reforc.vista === 'professor'"
          v-model="reforc.professor"
          :options="opcionsProfessorsReforc"
          optionLabel="nom"
          optionValue="nom"
          :placeholder="$t('groups.reforcPickTeacher')"
          :filter="true"
          filterBy="nom"
          class="reforc-teacher"
        >
          <template #option="{ option }">
            <span class="reforc-option">
              <span>{{ option.nom }}</span>
              <span class="reforc-count">{{ option.icona }} {{ option.amb }}/{{ option.total }}</span>
            </span>
          </template>
        </Dropdown>
        <label for="reforcData">{{ $t('groups.reforcFrom') }}</label>
        <InputText id="reforcData" v-model="reforc.data" type="date" />
      </div>
      <div class="reforc-toolbar reforc-toolbar-filtre">
        <div >
          <Checkbox v-model="reforc.nomesPendents" inputId="reforcPendents" :binary="true" />
          <label for="reforcPendents">{{ $t('groups.reforcOnlyPending') }}</label>
        </div>
        <span class="reforc-summary">{{ $t('groups.reforcSummary', resumReforc) }}</span>
      </div>
      <div class="reforc-legend">
        <span><span class="reforc-swatch"></span>○ {{ $t('groups.reforcLegendFree') }}</span>
        <span><span class="reforc-swatch amb"></span>● {{ $t('groups.reforcLegendBusy') }}</span>
      </div>

      <!-- Vista «Setmana»: hores × dies, amb els professors de cada franja -->
      <div v-if="reforc.vista === 'setmana'" class="reforc-tots">
        <table class="grups-table reforc-setmana">
          <thead>
            <tr>
              <th></th>
              <th v-for="dia in diesSetmana" :key="`s-${dia}`">{{ dia }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="hora in horesSetmana" :key="`s-${hora}`">
              <td class="grup-name">{{ hora }}</td>
              <td v-for="dia in diesSetmana" :key="`s-${dia}-${hora}`" class="reforc-setmana-cell">
                <button
                  v-for="f in frangesSetmana(dia, hora)"
                  :key="`s-${f.professor}-${dia}-${hora}`"
                  type="button"
                  class="reforc-slot reforc-slot-petit"
                  :class="{ amb: f.amb_alumnes }"
                  :disabled="reforc.desant"
                  :title="titolFranja(f)"
                  @click="canviaFranjaReforc(dia, hora, f.professor)"
                >
                  {{ f.amb_alumnes ? '●' : '○' }} {{ f.professor }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <table v-if="reforc.vista === 'professor' && reforc.professor" class="grups-table reforc-grid">
        <thead>
          <tr>
            <th></th>
            <th v-for="dia in diesReforc" :key="dia">{{ dia }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="hora in horesReforc" :key="hora">
            <td class="grup-name">{{ hora }}</td>
            <td v-for="dia in diesReforc" :key="`${dia}-${hora}`" class="checkbox-cell">
              <button
                v-if="frangaReforc(dia, hora)"
                type="button"
                class="reforc-slot"
                :class="{ amb: frangaReforc(dia, hora).amb_alumnes }"
                :disabled="reforc.desant"
                :title="titolFranja(frangaReforc(dia, hora))"
                @click="canviaFranjaReforc(dia, hora)"
              >
                <template v-if="frangaReforc(dia, hora).amb_alumnes">
                  ● {{ $t('groups.reforcBusy') }}<br /><small>{{ $t('groups.reforcSince', { data: dataCurta(frangaReforc(dia, hora).des_de) }) }}</small>
                </template>
                <template v-else>○ {{ $t('groups.reforcFree') }}</template>
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <template #footer>
        <Button :label="$t('common.close')" text severity="secondary" @click="reforc.visible = false" />
      </template>
    </Dialog>

    <!-- Canvis sense desar: Desa / No desis / Cancel·la -->
    <Dialog
      v-model:visible="avis.visible"
      :header="$t('common.unsavedChangesTitle')"
      modal
      :style="{ width: '28rem' }"
      @hide="respon('cancel')"
    >
      <p class="unsaved-message">
        <i class="pi pi-exclamation-triangle"></i>
        {{ $t('common.unsavedChangesQuestion', { dia: dataFormatada }) }}
      </p>
      <template #footer>
        <Button :label="$t('common.cancel')" text severity="secondary" @click="respon('cancel')" />
        <Button :label="$t('common.dontSave')" severity="danger" outlined @click="respon('descarta')" />
        <Button :label="$t('common.save')" severity="success" autofocus @click="respon('desa')" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Chip from 'primevue/chip'
import OverlayPanel from 'primevue/overlaypanel'
import Tag from 'primevue/tag'
import Message from 'primevue/message'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import { useGrups } from '../composables/useGrups'
import { useDialegsInterns } from '../dialegsInterns'

const toast = useToast()
const { t, locale } = useI18n()

const {
  hores,
  grupsDisponibles,
  checkboxes,
  panellProfessors,
  franja,
  activitatsMarcades,
  activitatsPerDefecte,
  reforcsDelDia,
  loading,
  desant,
  error,
  dataFormatada,
  estaOcupat,
  marcaOcupat,
  teCanvis,
  professorsDe,
  activitatsNoms,
  professorsActivitat,
  professorsReforcAvui,
  reforcAmbAlumnes,
  professorsFranja,
  dataCurta,
  estaAlliberat,
  alliberatsDe,
  alliberatsReforcAvui,
  lliuresReforcAvui,
  alliberatsActivitat,
  marcaProfessor,
  treureProfessor,
  obrirProfessors,
  resumProfessors,
  reforc,
  obrirReforc,
  frangaReforc,
  diesReforc,
  horesReforc,
  opcionsProfessorsReforc,
  diesSetmana,
  horesSetmana,
  frangesSetmana,
  titolFranja,
  resumReforc,
  canviaFranjaReforc,
  totalGrupsSeleccionats,
  totalHoresSeleccionades,
  onCheckboxChange,
  toggleGrupComplet,
  marcarTots,
  desmarcarTots,
  desarGrups,
  avis,
  respon,
  potSortir,
} = useGrups({ t, locale, toast })

// App.vue el crida abans de canviar de pestanya (també amb «Enrere»)
defineExpose({ potSortir, teCanvis })

// «Enrere» tanca el diàleg dels reforços com la creu (dialegsInterns.js)
useDialegsInterns({
  'grups-reforc': { obert: () => reforc.visible, tanca: () => { reforc.visible = false } },
})
</script>

<style scoped src="./grupsView.css"></style>
