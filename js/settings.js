let sharedInterests = {
  keywords: [],
  authors: [],
};
let interestsAvailable = true;

document.addEventListener('DOMContentLoaded', () => {
  initSettings();
  initEventListeners();
  fetchGitHubStats();
});

function normalizeInterestList(items) {
  if (!Array.isArray(items)) {
    return [];
  }

  const result = [];
  const seen = new Set();
  items.forEach(item => {
    if (typeof item !== 'string') {
      return;
    }
    const normalized = item.trim();
    if (!normalized) {
      return;
    }
    const key = normalized.toLowerCase();
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    result.push(normalized);
  });
  return result;
}

function normalizeInterests(interests) {
  return {
    keywords: normalizeInterestList(interests?.keywords),
    authors: normalizeInterestList(interests?.authors),
  };
}

// 初始化设置，从共享服务端加载已保存的设置
async function initSettings() {
  await loadSharedInterests();
  renderInterests();
}

async function loadSharedInterests() {
  try {
    const response = await fetch('/api/interests');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    sharedInterests = normalizeInterests(data);
    interestsAvailable = true;
  } catch (error) {
    console.error('Failed to load shared interests:', error);
    sharedInterests = { keywords: [], authors: [] };
    interestsAvailable = false;
    showNotification('Shared interests are unavailable. Start the site with python serve_local.py.', 'info');
  }
}

function renderInterests() {
  renderKeywordPreferences(sharedInterests.keywords);
  renderAuthorPreferences(sharedInterests.authors);
}

// 渲染关键词偏好
function renderKeywordPreferences(keywords = []) {
  const selectedKeywordsContainer = document.getElementById('selectedKeywords');
  selectedKeywordsContainer.innerHTML = '';

  // 显示保存的关键词
  if (keywords.length > 0) {
    keywords.forEach(keyword => {
      addKeywordTag(keyword);
    });
  } else {
    // 显示空标签消息
    showEmptyTagMessage();
  }
}

// 渲染作者偏好
function renderAuthorPreferences(authors = []) {
  const selectedAuthorsContainer = document.getElementById('selectedAuthors');
  selectedAuthorsContainer.innerHTML = '';

  // 显示保存的作者
  if (authors.length > 0) {
    authors.forEach(author => {
      addAuthorTag(author);
    });
  } else {
    // 显示空标签消息
    showEmptyAuthorMessage();
  }
}

// 显示空标签消息
function showEmptyTagMessage() {
  const selectedKeywordsContainer = document.getElementById('selectedKeywords');
  const emptyMessage = document.createElement('div');
  emptyMessage.id = 'emptyTagMessage';
  emptyMessage.className = 'empty-tag-message';
  emptyMessage.textContent = 'No keywords added yet. Add some keywords below.';
  selectedKeywordsContainer.appendChild(emptyMessage);
}

// 显示空作者标签消息
function showEmptyAuthorMessage() {
  const selectedAuthorsContainer = document.getElementById('selectedAuthors');
  const emptyMessage = document.createElement('div');
  emptyMessage.id = 'emptyAuthorMessage';
  emptyMessage.className = 'empty-tag-message';
  emptyMessage.textContent = 'No authors added yet. Add some authors below.';
  selectedAuthorsContainer.appendChild(emptyMessage);
}

// 隐藏空标签消息
function hideEmptyTagMessage() {
  const emptyMessage = document.getElementById('emptyTagMessage');
  if (emptyMessage) {
    emptyMessage.remove();
  }
}

// 隐藏空作者标签消息
function hideEmptyAuthorMessage() {
  const emptyMessage = document.getElementById('emptyAuthorMessage');
  if (emptyMessage) {
    emptyMessage.remove();
  }
}

// 添加关键词标签
function addKeywordTag(keyword) {
  const selectedKeywordsContainer = document.getElementById('selectedKeywords');
  
  // 移除空标签消息
  hideEmptyTagMessage();
  
  // 检查关键词是否已存在
  const existingTags = selectedKeywordsContainer.querySelectorAll('.category-button');
  for (let i = 0; i < existingTags.length; i++) {
    if (existingTags[i].textContent.trim().startsWith(keyword)) {
      // 已存在该关键词，添加闪烁动画提示用户
      existingTags[i].classList.add('tag-highlight');
      setTimeout(() => {
        existingTags[i].classList.remove('tag-highlight');
      }, 1000);
      return; // 关键词已存在，不添加
    }
  }
  
  // 创建新的关键词标签
  const tagElement = document.createElement('span');
  tagElement.className = 'category-button tag-appear';
  tagElement.innerHTML = `${keyword} <button class="remove-tag">×</button>`;
  
  // 添加删除按钮事件
  const removeButton = tagElement.querySelector('.remove-tag');
  removeButton.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    // 添加删除动画
    tagElement.classList.add('tag-disappear');
    
    // 动画结束后移除元素
    setTimeout(() => {
      tagElement.remove();
      
      // 如果没有标签了，显示空标签消息
      if (selectedKeywordsContainer.querySelectorAll('.category-button').length === 0) {
        showEmptyTagMessage();
      }
      saveSettings({ quiet: true });
    }, 300);
  });
  
  selectedKeywordsContainer.appendChild(tagElement);
  
  // 添加出现动画后移除动画类
  setTimeout(() => {
    tagElement.classList.remove('tag-appear');
  }, 300);
}

// 添加作者标签
function addAuthorTag(author) {
  const selectedAuthorsContainer = document.getElementById('selectedAuthors');
  
  // 移除空标签消息
  hideEmptyAuthorMessage();
  
  // 检查作者是否已存在
  const existingTags = selectedAuthorsContainer.querySelectorAll('.category-button');
  for (let i = 0; i < existingTags.length; i++) {
    if (existingTags[i].textContent.trim().startsWith(author)) {
      // 已存在该作者，添加闪烁动画提示用户
      existingTags[i].classList.add('tag-highlight');
      setTimeout(() => {
        existingTags[i].classList.remove('tag-highlight');
      }, 1000);
      return; // 作者已存在，不添加
    }
  }
  
  // 创建新的作者标签
  const tagElement = document.createElement('span');
  tagElement.className = 'category-button tag-appear';
  tagElement.innerHTML = `${author} <button class="remove-tag">×</button>`;
  
  // 添加删除按钮事件
  const removeButton = tagElement.querySelector('.remove-tag');
  removeButton.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    // 添加删除动画
    tagElement.classList.add('tag-disappear');
    
    // 动画结束后移除元素
    setTimeout(() => {
      tagElement.remove();
      
      // 如果没有标签了，显示空标签消息
      if (selectedAuthorsContainer.querySelectorAll('.category-button').length === 0) {
        showEmptyAuthorMessage();
      }
      saveSettings({ quiet: true });
    }, 300);
  });
  
  selectedAuthorsContainer.appendChild(tagElement);
  
  // 添加出现动画后移除动画类
  setTimeout(() => {
    tagElement.classList.remove('tag-appear');
  }, 300);
}

// 初始化事件监听器
function initEventListeners() {
  // 关键词添加按钮
  const addKeywordButton = document.getElementById('addKeyword');
  addKeywordButton.addEventListener('click', () => {
    const keywordInput = document.getElementById('keywordInput');
    const keyword = keywordInput.value.trim();

    if (keyword) {
      // 检测是否包含英文逗号，如果有则分割
      if (keyword.includes(',')) {
        const keywords = keyword.split(',').map(k => k.trim()).filter(k => k);
        keywords.forEach(k => addKeywordTag(k));
      } else {
        addKeywordTag(keyword);
      }
      keywordInput.value = '';
      saveSettings({ quiet: true });
    }
  });

  // 关键词输入框回车事件
  const keywordInput = document.getElementById('keywordInput');
  keywordInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const keyword = keywordInput.value.trim();

      if (keyword) {
        // 检测是否包含英文逗号，如果有则分割
        if (keyword.includes(',')) {
          const keywords = keyword.split(',').map(k => k.trim()).filter(k => k);
          keywords.forEach(k => addKeywordTag(k));
        } else {
          addKeywordTag(keyword);
        }
        keywordInput.value = '';
        saveSettings({ quiet: true });
      }
    }
  });

  // 作者添加按钮
  const addAuthorButton = document.getElementById('addAuthor');
  addAuthorButton.addEventListener('click', () => {
    const authorInput = document.getElementById('authorInput');
    const author = authorInput.value.trim();

    if (author) {
      // 检测是否包含英文逗号，如果有则分割
      if (author.includes(',')) {
        const authors = author.split(',').map(a => a.trim()).filter(a => a);
        authors.forEach(a => addAuthorTag(a));
      } else {
        addAuthorTag(author);
      }
      authorInput.value = '';
      saveSettings({ quiet: true });
    }
  });

  // 作者输入框回车事件
  const authorInput = document.getElementById('authorInput');
  authorInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const author = authorInput.value.trim();

      if (author) {
        // 检测是否包含英文逗号，如果有则分割
        if (author.includes(',')) {
          const authors = author.split(',').map(a => a.trim()).filter(a => a);
          authors.forEach(a => addAuthorTag(a));
        } else {
          addAuthorTag(author);
        }
        authorInput.value = '';
        saveSettings({ quiet: true });
      }
    }
  });

  // 关键词复制按钮
  const copyKeywordsButton = document.getElementById('copyKeywords');
  copyKeywordsButton.addEventListener('click', copyKeywords);

  // 作者复制按钮
  const copyAuthorsButton = document.getElementById('copyAuthors');
  copyAuthorsButton.addEventListener('click', copyAuthors);

  // 重置设置按钮
  const resetSettingsButton = document.getElementById('resetSettings');
  resetSettingsButton.addEventListener('click', resetSettings);
}

// 复制关键词到剪切板
function copyKeywords() {
  const keywordTags = document.getElementById('selectedKeywords').querySelectorAll('.category-button');
  const keywords = [];
  keywordTags.forEach(tag => {
    const keywordName = tag.textContent.trim().replace('×', '').trim();
    keywords.push(keywordName);
  });

  if (keywords.length === 0) {
    showNotification('No keywords to copy!', 'info');
    return;
  }

  const keywordsString = keywords.join(',');
  copyToClipboard(keywordsString, 'Keywords copied to clipboard!');
}

// 复制作者到剪切板
function copyAuthors() {
  const authorTags = document.getElementById('selectedAuthors').querySelectorAll('.category-button');
  const authors = [];
  authorTags.forEach(tag => {
    const authorName = tag.textContent.trim().replace('×', '').trim();
    authors.push(authorName);
  });

  if (authors.length === 0) {
    showNotification('No authors to copy!', 'info');
    return;
  }

  const authorsString = authors.join(',');
  copyToClipboard(authorsString, 'Authors copied to clipboard!');
}

// 复制到剪切板的通用函数
function copyToClipboard(text, successMessage) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showNotification(successMessage, 'success');
    }).catch(err => {
      console.error('复制失败:', err);
      fallbackCopyText(text, successMessage);
    });
  } else {
    fallbackCopyText(text, successMessage);
  }
}

// 后备复制方法（用于不支持 clipboard API 的浏览器）
function fallbackCopyText(text, successMessage) {
  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.style.position = 'fixed';
  textArea.style.left = '-9999px';
  document.body.appendChild(textArea);
  textArea.select();

  try {
    document.execCommand('copy');
    showNotification(successMessage, 'success');
  } catch (err) {
    console.error('复制失败:', err);
    showNotification('Failed to copy to clipboard', 'info');
  }

  document.body.removeChild(textArea);
}

function collectCurrentInterests() {
  // 获取所有选中的关键词
  const keywordTags = document.getElementById('selectedKeywords').querySelectorAll('.category-button');
  const keywords = [];
  keywordTags.forEach(tag => {
    const keywordName = tag.textContent.trim().replace('×', '').trim();
    keywords.push(keywordName);
  });
  
  // 获取所有选中的作者
  const authorTags = document.getElementById('selectedAuthors').querySelectorAll('.category-button');
  const authors = [];
  authorTags.forEach(tag => {
    const authorName = tag.textContent.trim().replace('×', '').trim();
    authors.push(authorName);
  });

  return normalizeInterests({ keywords, authors });
}

// 保存设置
async function saveSettings(options = {}) {
  if (!interestsAvailable) {
    showNotification('Shared interests are unavailable. Start the site with python serve_local.py.', 'info');
    return;
  }

  const nextInterests = collectCurrentInterests();
  try {
    const response = await fetch('/api/interests', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(nextInterests),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const savedInterests = await response.json();
    sharedInterests = normalizeInterests(savedInterests);
    renderInterests();
    if (!options.quiet) {
      showNotification('Shared interests saved!', 'success');
    }
  } catch (error) {
    console.error('Failed to save shared interests:', error);
    showNotification('Failed to save shared interests.', 'info');
  }
}

// 重置设置
function resetSettings() {
  // 重置关键词
  const selectedKeywordsContainer = document.getElementById('selectedKeywords');
  selectedKeywordsContainer.innerHTML = '';
  
  // 重置作者
  const selectedAuthorsContainer = document.getElementById('selectedAuthors');
  selectedAuthorsContainer.innerHTML = '';
  
  // 显示空标签消息
  showEmptyTagMessage();
  showEmptyAuthorMessage();
  
  // 显示重置成功提示
  saveSettings({ quiet: true });
  showNotification('Settings reset to default!', 'info');
}

// 显示通知
function showNotification(message, type = 'success') {
  // 检查是否已存在通知元素
  let notification = document.querySelector('.settings-notification');
  
  if (!notification) {
    // 创建通知元素
    notification = document.createElement('div');
    notification.className = 'settings-notification';
    document.body.appendChild(notification);
  }
  
  // 根据类型设置图标
  let icon = '';
  let bgColor = 'var(--primary-color)';
  
  if (type === 'success') {
    icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="currentColor"/></svg>';
  } else if (type === 'info') {
    icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 15c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1s1 .45 1 1v4c0 .55-.45 1-1 1zm1-8h-2V7h2v2z" fill="currentColor"/></svg>';
    bgColor = '#3b82f6';
  }
  
  // 设置通知内容和样式
  notification.innerHTML = `${icon}<span>${message}</span>`;
  notification.style.display = 'flex';
  notification.style.alignItems = 'center';
  notification.style.gap = '8px';
  notification.style.position = 'fixed';
  notification.style.bottom = '20px';
  notification.style.right = '20px';
  notification.style.backgroundColor = bgColor;
  notification.style.color = 'white';
  notification.style.padding = '12px 20px';
  notification.style.borderRadius = 'var(--radius-sm)';
  notification.style.boxShadow = 'var(--shadow-md)';
  notification.style.zIndex = '1000';
  notification.style.opacity = '0';
  notification.style.transform = 'translateY(20px)';
  notification.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
  
  // 显示通知
  setTimeout(() => {
    notification.style.opacity = '1';
    notification.style.transform = 'translateY(0)';
  }, 10);
  
  // 3秒后隐藏通知
  setTimeout(() => {
    notification.style.opacity = '0';
    notification.style.transform = 'translateY(20px)';
    
    // 动画结束后移除元素
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

// 获取GitHub统计数据
async function fetchGitHubStats() {
  try {
    const response = await fetch('https://api.github.com/repos/dw-dengwei/daily-arXiv-ai-enhanced');
    const data = await response.json();
    const starCount = data.stargazers_count;
    const forkCount = data.forks_count;
    
    document.getElementById('starCount').textContent = starCount;
    document.getElementById('forkCount').textContent = forkCount;
  } catch (error) {
    console.error('获取GitHub统计数据失败:', error);
    document.getElementById('starCount').textContent = '?';
    document.getElementById('forkCount').textContent = '?';
  }
} 