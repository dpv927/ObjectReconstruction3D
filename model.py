from view import View
import pyray as rl
import cv2
import os
import json
import numpy as np
import utils

class Model:

    """
    A model is a directory named with the format 'model_name' that contains 
    sub-directories named 'view..'. Each subdirectory must contain a file
    'plane.bmp' (tha image projection plane) and a 'camera.json' file with
    details about the camera position and angle.
    
    The requirements for the files plane.bmp are:
        
        - It must be a greyscale image, with only two colors: black and white (0/255)

        - The pixel at the center of the image must be the intersection point of a 
          perpendicular line to the projection plane that also passes at the origin 
          of the space (0,0,0). The line is the camera vision line and the point is
          the camera position.

    The requirements for the files camera.json are:

        - It must contain a object 'position', with three fields 'x', 'y', 'z', and
          the objects 'vx', 'vy', 'vz' with the same fields as 'position'.
        
        - 'position' describes the coordinate in space of the camera/projection plane 
          (same as the point described in the 'plane.bmp' file requirements).
        
        - 'vx', 'vy', 'vz' describe the 3 direction vectors of the projection plane.
          All of them are perpendicular to each other. 'vy' must follow the direction
          of the camera (up to the origin). 'vx' must be pointing to the right of the
          projection and 'vz' up of the projection. All vectors are normalized.

    If you dont understand how the direction of the vectors 'vx' and 'vz' work, just 
    think that they are the axis of the 2D image/projection ('vx' being the horizontal
    axis and 'vz' the vertical axis, 'vx' is positive to the right and vz 'up').
    """


    model_prefix = 'models/model_'
    camera_file = 'camera.json'
    image_view_file  = 'plane.bmp' 

    def __init__(self, model_name: str):
        model_name = self.model_prefix + model_name
        self.views = []
        self.vertices = []
        self.next_view = 0

        for view_dir in os.listdir(model_name):
            view_path = os.path.join(model_name, view_dir)

            if os.path.isdir(view_path) and view_dir.startswith('view'):
                # Obtener la imagen de la vista.
                img = cv2.imread(os.path.join(view_path, self.image_view_file), cv2.IMREAD_GRAYSCALE)
                
                # Obtener detalles de la posicion de la camara.
                with open(os.path.join(view_path, self.camera_file)) as file:
                    json_data = json.load(file)

                    data = json_data['position']
                    pos = rl.Vector3(data['x'], data['y'], data['z'])
                    
                    data = json_data['vx']
                    vx = rl.Vector3(data['x'], data['y'], data['z'])
                    
                    data = json_data['vy']
                    vy = rl.Vector3(data['x'], data['y'], data['z'])
                    
                    data = json_data['vz']
                    vz = rl.Vector3(data['x'], data['y'], data['z'])
                    self.views.insert(0, View(img, pos, vx, vy, vz))


    def initial_reconstruction(self):
        view0 = self.views[0]
        view1 = self.views[1]
        c = rl.vector3_cross_product(view0.vy, view1.vy)

        if c.x == 0 and c.y == 0 and c.z == 0:
          print("Both views have paralell vy vectors.")
          return
        self.next_view = 2

        # Calculate the intersections of the lines with direction vectors d0 and d1
        # (perpendicular to the image planes of views 0 and 1) and passing through
        # points p0 and p1 contained in each of the image planes.

        d0 = np.array([view0.vy.x, view0.vy.y, view0.vy.z])
        d1 = np.array([view1.vy.x, view1.vy.y, view1.vy.z])

        for p0 in view0.vertices:
            p0 = np.array([p0.x, p0.y, p0.z])
            
            for p1 in view1.vertices:
              p1 = np.array([p1.x, p1.y, p1.z])                
              a = np.array([d0, -d1]).T
              b = p1 - p0
              
              try:
                # Try to solve the both lines linear equation
                (t, s), _, _, _ = np.linalg.lstsq(a, b, rcond=None)
                p_inter1 = p0 + t * d0
                p_inter2 = p1 + s * d1

                if np.allclose(p_inter1, p_inter2):
                  self.vertices.insert(0, rl.Vector3(p_inter1[0], p_inter1[1], p_inter1[2]))
                else:
                  continue
              except np.linalg.LinAlgError:
                 continue
    

    def next_refinement_step(self):
      if self.next_view >= len(self.views):
        return False
      
      # Pick a point from the view plane and calculate the 'D' parameter
      # from the plane expresion Ax + By + Cz + D = 0. The A,B,C 
      # parameters are defined by the Vy direction vector of the view
      # (which is perpendicular to the view plane).
       
      view = self.views[self.next_view]
      plane_point = view.vertices[0]
      points_to_remove = []

      plane_d = utils.calculate_plane_d(
        plane_point.x, 
        plane_point.y,
        plane_point.z,
        view.vy.x,
        view.vy.y,
        view.vy.z
      )
      
      for point in self.vertices:
        plane_intersec = utils.intersect_plane_line(
          view.vy.x,
          view.vy.y,
          view.vy.z,
          plane_d,
          point.x,
          point.y, 
          point.z
        )
        
        # Remove the current model point if its not contained in the current view plane
        # (Its not visible in the current view).
        if not any(rl.vector3_equals(plane_intersec, view_point) for view_point in view.vertices):
            points_to_remove.insert(0, point)
      
      for point in points_to_remove:
        self.vertices.remove(point)

      self.next_view += 1
      return True
