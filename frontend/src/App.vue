<template>
  <div id="app">
    <Toast />

    <!-- Hi ha una versió nova al servidor (versioApp.js): cal recarregar -->
    <div v-if="versioNova" class="avis-versio" role="status">
      <span>{{ $t('app.newVersion') }}</span>
      <Button :label="$t('app.reload')" icon="pi pi-refresh" size="small" @click="recarregaPagina" />
    </div>

    <div v-if="!autenticat" class="login-screen">
      <div class="login-card">
        <h1 class="login-title">{{ $t('app.login.title') }}</h1>
        <p class="login-subtitle">{{ $t('app.login.subtitle') }}</p>

        <form class="login-form" @submit.prevent="ferLogin">
          <div class="login-field">
            <label for="login-user">{{ $t('app.login.username') }}</label>
            <InputText
              id="login-user"
              v-model="loginUser"
              autocomplete="username"

            />
          </div>
          <div class="login-field">
            <label for="login-pass">{{ $t('app.login.password') }}</label>
            <!-- PrimeVue posa id i autocomplete al contenidor: al camp hi van per inputId i inputProps -->
            <Password
              inputId="login-pass"
              v-model="loginPass"
              :feedback="false"
              class="password-with-eye"
              toggleMask
              :inputProps="{ autocomplete: 'current-password' }"
            />
          </div>

          <p v-if="loginError" class="login-error">{{ loginError }}</p>

          <Button
            type="submit"
            :label="$t('app.login.submit')"
            icon="pi pi-sign-in"
            :loading="loginLoading"
            :disabled="loginRetrySeconds !== null"
            class="login-submit"
          />
        </form>
      </div>
    </div>

    <div v-else>
      <SchedulerView
        v-if="isSchedulerRoute"
        @tornar-gestor="tornarAlGestor"
      />
      <template v-else>
      <!-- Navbar superior -->
      <header v-if="!isMobile" class="navbar">
        <div class="navbar-left">
          <div class="date-selector">
            <Button
              icon="pi pi-chevron-left"
              class="p-button-rounded p-button-text p-button-plain nav-date-btn"
              v-tooltip.bottom="$t('app.nav.prevDay')"
              @click="diaAnterior"
            />
            <Calendar :aria-label="$t('app.nav.selectDate')"
              v-model="dataSeleccionada"
              dateFormat="dd/mm/yy"
              :showIcon="true"
              :showButtonBar="true"
              :placeholder="$t('app.nav.selectDate')"
              :inputProps="{ autocomplete: 'nope', 'data-form-type': 'other', 'data-lpignore': 'true' }"
            />
            <Button
              icon="pi pi-chevron-right"
              class="p-button-rounded p-button-text p-button-plain nav-date-btn"
              v-tooltip.bottom="$t('app.nav.nextDay')"
              @click="diaSeguent"
            />
          </div>
        </div>

        <div class="navbar-center">
          <h1 class="logo">{{ $t('app.title') }}</h1>
          <div class="config-info" v-if="config">
            <span>👥 {{ $t('app.nav.teachers') }} {{ config.num_professors }}</span>
            <span>🕐 {{ $t('app.nav.hours') }} {{ config.num_hores }}</span>
            <span
              v-if="cursos.length"
              class="curs-indicador"
              :class="{ 'curs-indicador--cap': !cursDeLaData }"
              v-tooltip.bottom="$t('app.nav.course')"
            >
              📅 {{ cursDeLaData ? cursDeLaData.nom : $t('app.nav.courseNone') }}
            </span>
          </div>
        </div>

        <div class="navbar-right">
          <Button
            v-if="isAdmin"
            icon="pi pi-cog"
            class="p-button-rounded p-button-text p-button-plain"
            v-tooltip.bottom="$t('app.nav.settings')"
            @click="obrirConfiguracio"
          />
          <Button
            v-if="isAdmin"
            icon="pi pi-bolt"
            class="p-button-rounded p-button-text p-button-plain"
            v-tooltip.bottom="$t('app.nav.examSettings')"
            @click="obrirConfiguracioExamens"
          />
          <Button
            v-if="isAdmin"
            icon="pi pi-calendar"
            class="p-button-rounded p-button-text p-button-plain"
            v-tooltip.bottom="$t('app.nav.scheduler')"
            @click="anarScheduler"
          />
          <Button
            v-if="isAdmin"
            icon="pi pi-chart-bar"
            class="p-button-rounded p-button-text p-button-plain"
            v-tooltip.bottom="$t('app.nav.stats')"
            @click="obrirEstadistiques"
          />
          <Button
            icon="pi pi-user"
            class="p-button-rounded p-button-text p-button-plain"
            v-tooltip.bottom="$t('app.nav.profile')"
            @click="obrirPerfil"
          />
          <Button
            icon="pi pi-question-circle"
            class="p-button-rounded p-button-text p-button-plain"
            v-tooltip.bottom="$t('app.nav.help')"
            @click="obrirAjuda"
          />
          <Button
            icon="pi pi-sign-out"
            class="p-button-rounded p-button-text p-button-plain"
            v-tooltip.bottom="$t('app.nav.logout')"
            @click="ferLogout"
          />
        </div>
      </header>

      <header v-else class="mobile-header">
        <div class="mobile-header-top">
          <h1 class="logo">{{ $t('app.title') }}</h1>
          <Button
            icon="pi pi-bars"
            class="p-button-rounded p-button-text p-button-plain"
            v-tooltip.bottom="$t('app.nav.menu')"
            @click="mostrarMenuMobil = true"
          />
        </div>
        <div class="mobile-date-row">
          <Button
            icon="pi pi-chevron-left"
            class="p-button-rounded p-button-text p-button-plain nav-date-btn"
            v-tooltip.bottom="$t('app.nav.prevDay')"
            @click="diaAnterior"
          />
          <Calendar :aria-label="$t('app.nav.selectDate')"
            v-model="dataSeleccionada"
            dateFormat="dd/mm/yy"
            :showIcon="true"
            :showButtonBar="true"
            :placeholder="$t('app.nav.selectDate')"
            :inputProps="{ autocomplete: 'nope', 'data-form-type': 'other', 'data-lpignore': 'true' }"
          />
          <Button
            icon="pi pi-chevron-right"
            class="p-button-rounded p-button-text p-button-plain nav-date-btn"
            v-tooltip.bottom="$t('app.nav.nextDay')"
            @click="diaSeguent"
          />
        </div>
      </header>

      <!-- Tabs de navegació -->
      <div v-if="!isMobile" class="tabs-container">
        <div class="tabs">
          <button
            class="tab"
            :class="{ active: tabActiu === 'substitucions' }"
            @click="canviaTab('substitucions')"
          >
            {{ $t('app.tabs.substitucions') }}
          </button>
          <button
            class="tab"
            :class="{ active: tabActiu === 'grups' }"
            @click="canviaTab('grups')"
          >
            {{ $t('app.tabs.grups') }}
          </button>
          <button
            class="tab"
            :class="{ active: tabActiu === 'vigilancies' }"
            @click="canviaTab('vigilancies')"
          >
            {{ $t('app.tabs.vigilancies') }}
          </button>
        </div>
      </div>

      <!-- La demo és pública i compartida: qui hi entra ha de saber que el que
           escrigui el veuran altres visitants i que s'esborra cada nit. -->
      <div v-if="esDemo" class="demo-avis">
        <i class="pi pi-info-circle" aria-hidden="true"></i>
        <span>
          <strong>{{ $t('config.system.demoBannerTitle') }}.</strong>
          {{ $t('config.system.demoBannerText') }}
        </span>
      </div>

      <!-- Contingut -->
      <main class="main-content">
        <SubstitucionsView
          ref="substitucionsRef"
          v-if="tabActiu === 'substitucions'"
          :key="institucioKey"
          @anar-vigilancies="canviaTab('vigilancies')"
        />
        <GrupsView ref="grupsRef" v-if="tabActiu === 'grups'" :key="institucioKey" />
        <VigilanciesView v-if="tabActiu === 'vigilancies'" :key="institucioKey" @anar-substitucions="canviaTab('substitucions')" />
      </main>

      <nav v-if="isMobile" class="mobile-nav">
        <button
          class="mobile-nav-item"
          :class="{ active: tabActiu === 'substitucions' }"
          @click="canviaTab('substitucions')"
        >
          <i class="pi pi-list"></i>
          <span>{{ $t('app.tabs.substitucions') }}</span>
        </button>
        <button
          class="mobile-nav-item"
          :class="{ active: tabActiu === 'vigilancies' }"
          @click="canviaTab('vigilancies')"
        >
          <i class="pi pi-eye"></i>
          <span>{{ $t('app.tabs.vigilancies') }}</span>
        </button>
        <button
          class="mobile-nav-item"
          :class="{ active: tabActiu === 'grups' }"
          @click="canviaTab('grups')"
        >
          <i class="pi pi-users"></i>
          <span>{{ $t('app.tabs.grups') }}</span>
        </button>
        <button class="mobile-nav-item" @click="obrirPdfDia">
          <i class="pi pi-file-pdf"></i>
          <span>{{ $t('app.nav.pdfToday') }}</span>
        </button>
      </nav>

      <footer class="footer">
        <p>{{ $t('app.footer') }}</p>
      </footer>

      <!-- Diàlegs -->
      <!-- Canvis sense desar en tancar un diàleg (useConfirmaSortida.js) -->
      <ConfirmDialog :group="GRUP_SORTIDA" />
      <ConfiguracioDialog
        ref="configuracioRef"
        v-model:visible="mostrarConfiguracio"
        :currentRole="userProfile?.role"
        :currentInstitucio="userProfile?.institucio"
        @cursos-canviats="carregarCursos"
        @xml-importat="handleInstitucioCanviada"
      />
      <ConfiguracioExamensDialog ref="configuracioExamensRef" v-model:visible="mostrarConfiguracioExamens" />
      <EstadistiquesDialog
        v-model:visible="mostrarEstadistiques"
        :curs="cursDeLaData"
        :cursos="cursos"
      />
      <AjudaDialog v-model:visible="mostrarAjuda" />
      <ProfileDialog
        v-model:visible="mostrarPerfil"
        :username="userProfile?.username"
        :role="userProfile?.role"
        :institucio="userProfile?.institucio"
        @institucio-canviada="handleInstitucioCanviada"
      />

      <Dialog
        v-model:visible="mostrarMenuMobil"
        :header="$t('app.nav.menu')"
        :modal="true"
        :style="{ width: '320px' }"
      >
        <div class="mobile-menu">
          <Button
            v-if="isAdmin"
            icon="pi pi-cog"
            class="p-button-text"
            :label="$t('app.nav.settings')"
            @click="obrirConfiguracio(); mostrarMenuMobil = false"
          />
          <Button
            v-if="isAdmin"
            icon="pi pi-bolt"
            class="p-button-text"
            :label="$t('app.nav.examSettings')"
            @click="obrirConfiguracioExamens(); mostrarMenuMobil = false"
          />
          <Button
            v-if="isAdmin"
            icon="pi pi-calendar"
            class="p-button-text"
            :label="$t('app.nav.scheduler')"
            @click="anarScheduler(); mostrarMenuMobil = false"
          />
          <Button
            v-if="isAdmin"
            icon="pi pi-chart-bar"
            class="p-button-text"
            :label="$t('app.nav.stats')"
            @click="obrirEstadistiques(); mostrarMenuMobil = false"
          />
          <Button
            icon="pi pi-user"
            class="p-button-text"
            :label="$t('app.nav.profile')"
            @click="obrirPerfil(); mostrarMenuMobil = false"
          />
          <Button
            icon="pi pi-question-circle"
            class="p-button-text"
            :label="$t('app.nav.help')"
            @click="obrirAjuda(); mostrarMenuMobil = false"
          />
          <Button
            icon="pi pi-sign-out"
            class="p-button-text"
            :label="$t('app.nav.logout')"
            @click="ferLogout(); mostrarMenuMobil = false"
          />
        </div>
      </Dialog>
      </template>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'
import Calendar from 'primevue/calendar'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Dialog from 'primevue/dialog'
import ConfirmDialog from 'primevue/confirmdialog'
import SubstitucionsView from './views/SubstitucionsView.vue'
import GrupsView from './views/GrupsView.vue'
import VigilanciesView from './views/VigilanciesView.vue'
import SchedulerView from './views/SchedulerView.vue'
import ConfiguracioDialog from './components/ConfiguracioDialog.vue'
import ConfiguracioExamensDialog from './components/ConfiguracioExamensDialog.vue'
import EstadistiquesDialog from './components/EstadistiquesDialog.vue'
import AjudaDialog from './components/AjudaDialog.vue'
import ProfileDialog from './components/ProfileDialog.vue'
import { useAplicacio } from './composables/useAplicacio'
import { GRUP_SORTIDA } from './composables/useConfirmaSortida'

const { t } = useI18n()
const toast = useToast()

const {
  config,
  autenticat,
  tabActiu,
  grupsRef,
  configuracioRef,
  configuracioExamensRef,
  canviaTab,
  substitucionsRef,
  dataSeleccionada,
  mostrarConfiguracio,
  mostrarConfiguracioExamens,
  mostrarEstadistiques,
  mostrarAjuda,
  mostrarPerfil,
  mostrarMenuMobil,
  loginUser,
  loginPass,
  loginError,
  loginLoading,
  loginRetrySeconds,
  isMobile,
  userProfile,
  institucioKey,
  isAdmin,
  esDemo,
  isSchedulerRoute,
  cursos,
  cursDeLaData,
  carregarCursos,
  handleInstitucioCanviada,
  tornarAlGestor,
  anarScheduler,
  versioNova,
  recarregaPagina,
  ferLogin,
  ferLogout,
  obrirConfiguracio,
  obrirConfiguracioExamens,
  obrirEstadistiques,
  obrirPerfil,
  obrirAjuda,
  obrirPdfDia,
  diaAnterior,
  diaSeguent,
} = useAplicacio({ t, toast })
</script>

<style src="./app.css"></style>
