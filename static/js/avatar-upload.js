/**
 * avatar-upload.js
 *
 * Handles the profile avatar crop-and-upload flow:
 *  1. User selects a file via #avatar-input
 *  2. The crop modal opens, showing the image in Cropper.js
 *  3. On confirm, the Canvas API produces a square blob
 *  4. The blob is POSTed to /profile/upload-avatar/
 *  5. On success, the avatar <img> is updated in-place (no full reload)
 */

(function () {
  "use strict";

  const input = document.getElementById("avatar-input");
  const modal = document.getElementById("avatar-crop-modal");
  const cropImg = document.getElementById("avatar-crop-image");
  const confirmBtn = document.getElementById("avatar-crop-confirm");
  const cancelBtn = document.getElementById("avatar-crop-cancel");
  const errorMsg = document.getElementById("avatar-upload-error");
  const avatarDisplay = document.getElementById("avatar-display");

  if (!input || !modal) return;

  let cropper = null;
  const uploadUrl = input.dataset.uploadUrl;
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;

  function showError(msg) {
    if (errorMsg) {
      errorMsg.textContent = msg;
      errorMsg.hidden = false;
    }
  }

  function clearError() {
    if (errorMsg) {
      errorMsg.textContent = "";
      errorMsg.hidden = true;
    }
  }

  input.addEventListener("change", function (e) {
    const file = e.target.files[0];
    if (!file) return;

    clearError();

    const reader = new FileReader();
    reader.onload = function (ev) {
      cropImg.src = ev.target.result;

      // Destroy any previous Cropper instance
      if (cropper) {
        cropper.destroy();
        cropper = null;
      }

      modal.showModal();

      cropper = new Cropper(cropImg, {
        aspectRatio: 1,
        viewMode: 1,
        dragMode: "move",
        autoCropArea: 0.8,
        restore: false,
        guides: true,
        center: true,
        highlight: false,
        cropBoxMovable: true,
        cropBoxResizable: true,
        toggleDragModeOnDblclick: false,
        preview: "#avatar-crop-preview",
      });
    };
    reader.readAsDataURL(file);
    // Reset input so re-selecting the same file triggers change again
    input.value = "";
  });

  cancelBtn.addEventListener("click", function () {
    modal.close();
    if (cropper) {
      cropper.destroy();
      cropper = null;
    }
  });

  // Close on backdrop click
  modal.addEventListener("click", function (e) {
    if (e.target === modal) {
      modal.close();
      if (cropper) {
        cropper.destroy();
        cropper = null;
      }
    }
  });

  confirmBtn.addEventListener("click", function () {
    if (!cropper) return;

    confirmBtn.disabled = true;
    confirmBtn.textContent = "Uploading…";

    const canvas = cropper.getCroppedCanvas({ width: 512, height: 512 });
    canvas.toBlob(
      function (blob) {
        const formData = new FormData();
        formData.append("avatar", blob, "avatar.jpg");

        fetch(uploadUrl, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken },
          body: formData,
        })
          .then(function (resp) {
            return resp.json().then(function (data) {
              return { ok: resp.ok, data };
            });
          })
          .then(function ({ ok, data }) {
            if (ok && data.avatar_url) {
              // Update avatar image(s) on the page
              if (avatarDisplay) {
                avatarDisplay.src = data.avatar_url + "?t=" + Date.now();
              }
              document.querySelectorAll(".avatar-live").forEach(function (img) {
                img.src = data.avatar_url + "?t=" + Date.now();
              });
              modal.close();
              if (cropper) {
                cropper.destroy();
                cropper = null;
              }
            } else {
              showError(data.error || "Upload failed. Please try again.");
            }
          })
          .catch(function () {
            showError("Network error. Please try again.");
          })
          .finally(function () {
            confirmBtn.disabled = false;
            confirmBtn.textContent = "Use this photo";
          });
      },
      "image/jpeg",
      0.92
    );
  });
})();
